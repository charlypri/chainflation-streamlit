
import pandas as pd
import pymongo
from datetime import datetime, timedelta
from typing import Dict

pd.set_option("display.max_columns", None)

DATABASE = "chainflation"

year_date = datetime.now() - timedelta(days=730)

def getAlimentacionJson():
    """
    Fetches alimentacion records from the MongoDB collection and returns them as a list of dictionaries.

    Returns:
        list: A list of dictionaries containing alimentacion records.
    """
    myclient = pymongo.MongoClient("mongodb+srv://cprietof:INcamachaja9@chainflation-east.eoueeme.mongodb.net/?retryWrites=true&w=majority")
    mydb = myclient[DATABASE]

    alim_collect = mydb["alimentacion"]
    cursor  = alim_collect.find({"fecha": {"$gte": year_date}},{"_id":0, 'fecha': 1, 'producto': 1, 'precio_referencia': 1, 'tienda': 1}).sort("fecha", 1)
    records = list(cursor)
    
    return records

def getViviendaJson():
    """
    Fetches vivienda records from the MongoDB collection and returns them as a list of dictionaries.

    Returns:
        list: A list of dictionaries containing vivienda records.
    """
    myclient = pymongo.MongoClient("mongodb+srv://cprietof:INcamachaja9@chainflation-east.eoueeme.mongodb.net/?retryWrites=true&w=majority")
    mydb = myclient[DATABASE]

    alim_collect = mydb["vivienda"]
    cursor  = alim_collect.find({"fecha": {"$gte": year_date}},{"_id":0, 'fecha': 1, 'tipo': 1, 'provincia':1, 'precio': 1, 'fuente': 1}).sort("fecha", 1)
    records = list(cursor)
    
    return records

def getEnergiaJson():
    """
    Fetches energia records from the MongoDB collection and returns them as a list of dictionaries.

    Returns:
        list: A list of dictionaries containing energia records.
    """
    myclient = pymongo.MongoClient("mongodb+srv://cprietof:INcamachaja9@chainflation-east.eoueeme.mongodb.net/?retryWrites=true&w=majority")
    mydb = myclient[DATABASE]
    
    alim_collect = mydb["energia"]
    cursor  = alim_collect.find({"fecha": {"$gte": year_date}},{"_id":0, 'fecha': 1, 'combustible': 1,  'precio': 1, 'fuente': 1}).sort("fecha", 1)
    records = list(cursor)
    
    return records


def getProductPrices() -> Dict[str, pd.DataFrame]:
    """
    Get product prices from different sectors.

    Returns:
        Dict[str, pd.DataFrame]: A dictionary containing DataFrames with product prices
                                 for 'energia', 'vivienda', and 'alimentacion' sectors.
    """

    prod_prices = {}

    prod_prices['energia'] = pd.json_normalize(getEnergiaJson())
    prices_vivienda = pd.json_normalize(getViviendaJson())
    prod_prices['vivienda'] = prices_vivienda.loc[~((prices_vivienda['fuente'] == 'idealista') & (prices_vivienda['provincia'] == 'Madrid'))].copy()
    prod_prices['alimentacion'] = pd.json_normalize(getAlimentacionJson())
    prod_prices['alimentacion']["precio"] = prod_prices['alimentacion']["precio_referencia"] 

    prod_prices['energia'].rename(columns = {'combustible':'producto'}, inplace = True)
    prod_prices['vivienda'].rename(columns = {'tipo':'producto'}, inplace = True)
    prod_prices['alimentacion'].rename(columns = {'tienda':'fuente'}, inplace = True)

    return prod_prices

def calc_monthly_mean_prices(daily_prices: pd.DataFrame, cols) -> pd.DataFrame:
    """
    Calculate the monthly mean prices from daily prices.

    Args:
        daily_prices (pd.DataFrame): DataFrame containing daily prices.

    Returns:
        pd.DataFrame: DataFrame with monthly mean prices.
    """
    
    daily_prices['month'] = daily_prices['fecha'].dt.month
    daily_prices['year'] = daily_prices['fecha'].dt.year

    # Group the data by 'product', 'year', and 'month' and calculate the average price for each group
    daily_average_prices = daily_prices.groupby(cols)['precio'].mean().reset_index()
    return daily_average_prices

def get_monthly_mean_with_date(product_data, group_columns):
    monthly_data = calc_monthly_mean_prices(product_data, group_columns)
    monthly_data['fecha'] = pd.to_datetime(monthly_data[['year', 'month']].assign(day=1))
    return monthly_data


def update_bronze_layer():
    # get product prices
    prod_prices  = getProductPrices()

    monthly_prices = {
        'vivienda': get_monthly_mean_with_date(prod_prices['vivienda'], ['producto', 'provincia', 'fuente', 'year', 'month']),
        'alimentacion': get_monthly_mean_with_date(prod_prices['alimentacion'], ['producto', 'fuente', 'year', 'month']),
        'energia': get_monthly_mean_with_date(prod_prices['energia'], ['producto', 'fuente', 'year', 'month'])
    }

    myclient = pymongo.MongoClient("mongodb+srv://cprietof:INcamachaja9@chainflation-east.eoueeme.mongodb.net/?retryWrites=true&w=majority")
    mydb = myclient[DATABASE]

    # Check and update data in MongoDB collections
    for product, data in monthly_prices.items():
        collection = mydb[f"{product}_monthly"]
        data_columns = data.columns.tolist()
        
        # Get the latest date from the existing records in MongoDB
        latest_record = collection.find_one({}, sort=[('fecha', pymongo.DESCENDING)])
        if latest_record:
            last_month = latest_record['fecha'].replace(day=1)
            last_month_data = data[data['fecha'] >= last_month]
            
            # Check if there are any records to update for the last month
            if not last_month_data.empty:
                # Update the existing records for the last month
                for _, record in last_month_data.iterrows():
                    filter_dict = {col: record[col] for col in data_columns if col != 'precio'}
                    collection.update_one(filter_dict, {'$set': {'precio': record['precio']}})
                    print("updated one record")
            else:
                # There are no new records to update, so skip this product
                print("No data to update")
                continue
        else:
            # No existing records, insert all new records
            collection.insert_many(data.to_dict(orient='records'))
            print("initial ingestion")
            print(f"Ingesting {product} data: {data.shape}")

    return
