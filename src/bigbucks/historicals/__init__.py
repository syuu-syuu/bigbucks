import yfinance as yf
from bigbucks.model import sp500data, FiveYearHoldings, Stock
from bigbucks import database



def update_sp500_data():
    database.session.query(sp500data).delete()
    database.session.commit()    
    sp500 = yf.Ticker("^GSPC")
    hist_data = sp500.history(period="5y")
    for index, row in hist_data.iterrows():
        sp5005yr = sp500data(
            date = index.date(),
            open = row["Open"],
            high = row["High"],
            low = row["Low"],
            close = row["Close"],
            volume = row["Volume"],
        )
        database.session.add(sp5005yr)
    database.session.commit()


def update_portfolio_history_data():
    database.session.query(FiveYearHoldings).delete()
    database.session.commit()    
    unique_stocks =  database.session.query(Stock.stock_symbol).distinct().all()
    unique_stock_list = [stock[0] for stock in unique_stocks]
    for stock in unique_stock_list:
        stock_query = yf.Ticker(stock)
        hist_data = stock_query.history(period="5y")
        for index, row in hist_data.iterrows():
            Portfolio5yr = FiveYearHoldings(
                date = index.date(),
                open = row["Open"],
                high = row["High"],
                low = row["Low"],
                close = row["Close"],
                volume = row["Volume"],
            )
            database.session.add(Portfolio5yr)
    database.session.commit()
