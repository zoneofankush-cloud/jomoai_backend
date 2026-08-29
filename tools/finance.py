import asyncio, requests
from langchain.tools import tool
import yfinance as yf

@tool
async def stock_price(symbol: str):
    """Get stock price. Use NSE format like 'HDFCBANK.NS' for Indian stocks, or ticker symbol like 'AAPL' for US stocks."""
    def _fetch():
        x = yf.Ticker(symbol).history(period='1d')
        return {f'stock_price for {symbol}': x['Close']}

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        return {"error": f"Could not fetch stock price: {str(e)}"}

@tool
def conversion_factor(base_currency: str, target_currency: str, base_currency_value: float = 1.0):
    """ 
    This function fetches the currency conversion factor between a given base currency and a target currency
    args: 
        required: 
            base_currency: str,
            target_currency: str,
            base_currency_value: float
    returns: 
       dict with the conversion factor and the converted value of the given currency
    """
    try:
        url = f"https://open.er-api.com/v6/latest/{base_currency.upper()}"
        response = requests.get(url)
        data   = response.json()
        target = data["rates"][target_currency.upper()]
        time   = data['time_last_update_utc']
        return {
            "timestamp":         time,
            "base_currency":     base_currency.upper(),
            "target_currency":   target_currency.upper(),
            "conversion_factor":  target,
            "converted_value": base_currency_value * target
        }
    except Exception as e:
        return f"Error fetching currency conversion, try search tool instead, error: {e}"