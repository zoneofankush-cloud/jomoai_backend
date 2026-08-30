# graph.py
#=================================================================
#========================  PATH IMPORTS  =========================
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.sandbox import python_docker_sandbox
from tools.core import demand_history, time_tool, search_tool, fetch_webpage
from tools.emails import Send_Email, fetch_emails
from tools.finance import stock_price, conversion_factor
from tools.files import read_document,load_pdf_document,ipynb_file_reader,\
                        read_image, read_excel_file, read_html_file, read_xml_file
from tools.youtube import search_youtube, youtube_video_transcript

# ===== CHANGED: github_user + asyncio.run() hardcoded startup load hataya =====
# ===== CHANGED: generic get_mcp_tools + PROVIDER_CONFIGS import kiya =====
from tools.mcp_clients.basic import get_mcp_tools_for_user, PROVIDER_CONFIGS

#=================================================================
#=======================  Module Imports =========================
from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from pydantic import BaseModel, Field
from typing import List
import time

def get_text(content):
    if isinstance(content, list):
        return "".join(x.get("text", "") for x in content if isinstance(x, dict))
    else:
        return content

#=================================================================
#=======================  Persistent Nodes =======================
class UserFact(BaseModel):
    topic: str = Field(..., description="Single topic (e.g., 'Location', 'Career Goal', 'Tech Stack')")
    info: str = Field(..., description="Details about that specific topic")

class check_message(BaseModel):
    should_record: bool = Field(..., description="Return True if User has provided any New Info")
    extracted_facts: List[UserFact] = Field(default_factory=list, description="List of all distinct facts found in the message")

async def memory_state(state: MessagesState, store: BaseStore, config: RunnableConfig):
    selected_llm = config['configurable']['llm'] # type: ignore
    structured_model = selected_llm.with_structured_output(check_message)

    user_id = config['configurable']['user_id'] # type: ignore
    user_message = None
    for message in reversed(state["messages"]):
        if getattr(message, "type", None) in {"human", "user"}:
            user_message = get_text(message.content)
            break
    user_details = ('profile', user_id, 'details')
    user_info = await store.asearch(user_details)
    user_old_info = ''.join([f"\n- {x.key}: {x.value['data']}" for x in user_info])
    prompt = f"""user has given this information: {user_message}\n
    check is this info match with already save info:{user_old_info}\n,
    if yes return False otherwise return True
    if it is mix of match like old info partially match the new info 
    return True and give a consised info about user by excluding the user's old info in list.
    """
    ai_response = await structured_model.ainvoke(prompt)
    if ai_response.should_record == True:
        for fact in ai_response.extracted_facts:
            await store.aput(user_details, fact.topic, {'data': fact.info})
    return {}

# ===== CHANGED: 'tools' se 'STATIC_TOOLS' rename — MCP tools ab yahan baked-in nahi, dynamic hain =====
STATIC_TOOLS = [demand_history, time_tool, stock_price, conversion_factor, ipynb_file_reader, read_image, 
         read_excel_file, read_html_file, read_xml_file, search_tool, fetch_webpage,
         python_docker_sandbox, fetch_emails, Send_Email, read_document, load_pdf_document,
         search_youtube, youtube_video_transcript]

# ===== CHANGED: global 'tool_node = ToolNode(tools)' hataya, iski jagah per-request function =====
# ===== NEW: execution time pe bhi sahi user ke tokens use hote hain, sab users ka shared nahi =====
async def tools_node(state: MessagesState, config: RunnableConfig):
    user_id = config['configurable']['user_id']  # type: ignore
    mcp_tools = []
    for mcp_name in PROVIDER_CONFIGS:
        mcp_tools.extend(await get_mcp_tools_for_user(user_id, mcp_name))
    node = ToolNode(STATIC_TOOLS + mcp_tools)
    return await node.ainvoke(state, config)

#=================================================================
#===================== Dynamic Tool Selection ====================
# ===== NEW: MCP provider keywords bhi ab config-driven, naya provider add karna ek line hi hai =====
MCP_KEYWORDS = {
    "github": ["github", "repo", "git", "copilot"],
    "context7": ["context7", "context", "search", "code"]
}

# ===== CHANGED: sync se async, user_id param add =====
async def select_active_tools(user_query: str, user_id: str):
    user_query = user_query.lower()
    
    active_tools = [demand_history, time_tool, search_tool, fetch_webpage]
    
    if any(keyword in user_query for keyword in ["stock", "price", "market", "finance"]):
        active_tools.append(stock_price)
    
    if any(keyword in user_query for keyword in ["conversion", "rate", "currency", "market", "factor", "exchange", "INR", "USD"]):
        active_tools.append(conversion_factor)

    if any(keyword in user_query for keyword in ["youtube", "suggest", "video"]):
            active_tools.extend([search_youtube, youtube_video_transcript])
        
    if any(keyword in user_query for keyword in ["email", "mail", "inbox"]):
        active_tools.extend([fetch_emails, Send_Email])
        
    if any(keyword in user_query for keyword in ["file", "pdf", "image", "excel", "csv", "html", "xml", "read", "document"]):
        active_tools.extend([
            read_document, load_pdf_document, read_image, 
            read_excel_file, read_html_file, read_xml_file, ipynb_file_reader
        ])
        
    if any(keyword in user_query for keyword in ["code", "run", "python", "script", "sandbox"]):
        active_tools.append(python_docker_sandbox)
        
    # ===== CHANGED: hardcoded github_tools_list ki jagah generic MCP_KEYWORDS loop =====
    for mcp_name, keywords in MCP_KEYWORDS.items():
        if any(k in user_query for k in keywords):
            active_tools.extend(await get_mcp_tools_for_user(user_id, mcp_name))
        
    return active_tools


#=================================================================
#=========================  Get Time =============================
def get_local_time(user_tz):
    try:
        from zoneinfo import ZoneInfo
        import datetime
        return datetime.datetime.now(ZoneInfo(user_tz)).strftime("%A, %Y-%m-%d %H:%M:%S %Z")
    except Exception:
        import time
        return str(time.localtime())


#=================================================================
#=========================  Chat State ===========================
async def chat_node(state: MessagesState, store: BaseStore, config: RunnableConfig):
    selected_llm = config['configurable']['llm'] # type: ignore
    if not state['messages']:
        return {'messages': []}
        
    last_human_idx = 0
    for i in range(len(state['messages']) - 1, -1, -1):
        if isinstance(state['messages'][i], HumanMessage):
            last_human_idx = i
            break
            
    user_query_text = get_text(state['messages'][last_human_idx].content)

    #=================================================================
    #=========================  Direct Response ======================
    user_query_lower = user_query_text.lower().strip()

    simple_greetings = ["hi", "hello", "hey", "thanks", "ok"]
    if user_query_lower in simple_greetings:
        response = await selected_llm.ainvoke(user_query_text)
        return {'messages': [response]}

    #=================================================================
    #==================  Gather and Config User Info =================
    user_id = config['configurable']['user_id'] # type: ignore
    user_location = config['configurable']['location'] # type: ignore
    user_tz = config['configurable']['timezone'] # type: ignore
    current_time_str = get_local_time(user_tz)
    user_details = ('profile', user_id, 'details')
    user_info = await store.asearch(user_details)

    if user_info:
        info = ''.join([f"\n- {x.key}: {x.value['data']}" for x in user_info])
    else:
        info = ""
    
    sys_config = {"name": "jomoai", "version": 'v-01', "established": "15 August 2026", "trained by": "Ankush Gautam"}
    sys_msg    = SystemMessage(content=f"{str(sys_config)}\nuser_info: \n{info} \n- current_location: {user_location}\n- current_time: {current_time_str}")
    #=================================================================
    #========== Sliding Window + Unified Truncation ==================
            
    # 2. Current turn (Sawal aur uske saare tool calls) ko hamesha safe rakho
    current_turn_messages = state['messages'][last_human_idx:]
    
    # 3. Purani history me se sirf aakhiri 4-6 messages lo
    past_messages = state['messages'][:last_human_idx]
    recent_past = past_messages[-4:] if past_messages else []
    
    # 4. Dono ko mila do
    recent_messages = recent_past + current_turn_messages

    safe_messages = []
    for msg in recent_messages:
        text_content = get_text(msg.content)
        if text_content and len(text_content) > 4000:
            truncated_text = text_content[:4000] + "\n\n...[Context truncated]"
            safe_messages.append(msg.model_copy(update={"content": truncated_text}))
        else:
            safe_messages.append(msg)

    #=================================================================  
    #==================== API CRASH PROTECTION =======================
    while len(safe_messages) > 0 and not isinstance(safe_messages[0], HumanMessage):
        safe_messages.pop(0)
        
    if len(safe_messages) == 0:
        safe_messages = [HumanMessage(content="Continue.")]

    #=================================================================
    #========================= FINAL CALL ============================
    # ===== CHANGED: await + user_id pass, kyunki select_active_tools ab async hai =====
    active_tools = await select_active_tools(user_query_text, user_id)
    llm_tool = selected_llm.bind_tools(active_tools)
    # Yeh direct poora lamba message return hone ka wait karta tha
    response = await llm_tool.ainvoke([sys_msg] + safe_messages, config)
    return {'messages': [response]}
    
#=================================================================
#=======================  GRAPH STATE ============================
async def graph_state(checkpoint, store):
    graph = StateGraph(MessagesState)
    graph.add_node('chat_node', chat_node)
    graph.add_node("store_node", memory_state) 
    # ===== CHANGED: 'tool_node' (global) → 'tools_node' (per-request, per-user) =====
    graph.add_node('tools', tools_node)
    graph.add_edge(START, 'chat_node')
    graph.add_conditional_edges('chat_node', tools_condition,{
        "tools": "tools", END: "store_node"
        })
    graph.add_edge('tools', 'chat_node')
    graph.add_edge('store_node', END)
    workflow = graph.compile(checkpointer=checkpoint, store=store)
    return workflow

#=================================================================
#=========================  TITLE STATE ==========================
class PromptSummary(BaseModel):
        prompt: str = Field(..., description="Give a 3 to 5 words discription of prompt")

async def chat_heading(prompt, selected_llm):    
    structured_llm = selected_llm.with_structured_output(PromptSummary)
    prompt_template = PromptTemplate(
        template="Based on user following prompt summarise it in 3 to 5 words: {user_prompts}",
        input_variables=["user_prompts"]
    )
    chain = prompt_template | structured_llm
    result = await chain.ainvoke({"user_prompts": prompt})
    return result.prompt
