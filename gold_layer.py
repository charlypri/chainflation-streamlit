
from datetime import datetime, timedelta
import pandas as pd
import pymongo
from typing import Dict
import streamlit as st

DATABASE = "chainflation"

def get_previous_date(date, time_frame):

    if time_frame == 'year':
        # Calculate the previous year's date
        previous_date = date - timedelta(days=365)
    elif time_frame == 'month':
        # Calculate the previous month's date
        year = date.year
        month = date.month
        if month == 1:
            # If the current month is January, set the previous month to December of the previous year
            previous_date = date.replace(year=year-1, month=12)
        else:
            # Otherwise, set the previous month to the previous month of the same year
            previous_date = date.replace(month=month-1)
    else:
        raise ValueError("Invalid time frame. It should be either 'year' or 'month'.")

    return previous_date

def calc_monthly_inflation(sector_df, cols, time_frame='year'):
    """
    Calculate inflation for each product and source in the given sector DataFrame.

    The function calculates the inflation for each product and its corresponding source
    by comparing the average prices of the products `ago` days ago with the prices
    on the last recorded day.

    Args:
        sector_df (pd.DataFrame): DataFrame containing sector data with columns 'fecha',
                                  'producto', 'fuente', and 'precio'.
        ago (int): Number of days to compare the prices with.

    Returns:
        pd.DataFrame: DataFrame containing inflation data with columns 'producto', 'fuente',
                      'fecha', and 'inflation'.
    """
    # Keep only Year, Month, Day in the 'fecha' column
    sector_df.fecha = sector_df.fecha.apply(lambda x: datetime(x.year, x.month, x.day))

    total_dates = sector_df.fecha.dt.date.unique()
    join_on = [item for item in cols if item != "fecha"]

    monthly_inflation_products = pd.DataFrame()
    
    for date in total_dates:
        previous_date = get_previous_date(date=date, time_frame=time_frame)
        current_prices = sector_df[(sector_df['month'] == date.month) & (sector_df['year'] == date.year)].groupby(cols).mean(numeric_only=True).sort_values(by=['producto']).reset_index()
        previous_prices = sector_df[(sector_df['month'] == previous_date.month) & (sector_df['year'] == previous_date.year)].groupby(cols).mean(numeric_only=True).sort_values(by=['producto']).reset_index()

        if len(current_prices) == 0 or len(previous_prices) == 0:
            continue
        
        
        prices = pd.merge(previous_prices, current_prices, on=join_on, how='inner', suffixes=('_ref', ''))
        prices["inflation"] = ((prices["precio"] - prices["precio_ref"]) / prices["precio_ref"]) * 100
        monthly_inflation_products = pd.concat([monthly_inflation_products, prices], ignore_index=True)

    # monthly_inflation_products.drop(["precio_ref","fecha_ref"], axis=1, inplace=True)
    return monthly_inflation_products

def update_monthly_inflation_per_product(include_source=False):
    # Read data from MongoDB collections
    myclient = pymongo.MongoClient(st.secrets["DB_SECRET"])
    mydb = myclient[DATABASE]

    vivienda_monthly = pd.json_normalize(list(mydb["vivienda_monthly"].find()))
    alimentacion_monthly = pd.json_normalize(list(mydb["alimentacion_monthly"].find()))
    energia_monthly = pd.json_normalize(list(mydb["energia_monthly"].find()))


    # Convert 'fecha' column to datetime
    vivienda_monthly['fecha'] = pd.to_datetime(vivienda_monthly['fecha'])
    alimentacion_monthly['fecha'] = pd.to_datetime(alimentacion_monthly['fecha'])
    energia_monthly['fecha'] = pd.to_datetime(energia_monthly['fecha'])

    if include_source:
        cols = ["producto", "fuente", "fecha"]
        collection = mydb["YoY_inflation_per_prod_source"]
    else:
        cols = ["producto", "fecha"]
        collection = mydb["YoY_inflation_per_prod"]
    # Calculate yearly inflation per source for each product
    monthly_inflation_prod_source = {
        'vivienda': calc_monthly_inflation(vivienda_monthly, cols=cols, time_frame='year'),
        'alimentacion': calc_monthly_inflation(alimentacion_monthly, cols=cols, time_frame='year'),
        'energia': calc_monthly_inflation(energia_monthly, cols=cols, time_frame='year')
    }

    # Concatenate DataFrames and add 'product' field
    all_data = pd.concat([monthly_inflation_prod_source[sector].assign(sector=sector) for sector in monthly_inflation_prod_source.keys()])

    data_columns = all_data.columns.tolist()
    
    # Get the latest date from the existing records in MongoDB
    latest_record = collection.find_one({}, sort=[('fecha', pymongo.DESCENDING)])
    if latest_record:
        last_month = latest_record['fecha'].replace(day=1)
        last_month_data = all_data[all_data['fecha'] >= last_month]
        
        # Check if there are any records to update for the last month
        if not last_month_data.empty:
            # Update the existing records for the last month
            for _, record in last_month_data.iterrows():
                filter_dict = {col: record[col] for col in data_columns if col != 'precio'}
                collection.update_one(filter_dict, {'$set': {'precio': record['precio']}}, upsert=True)
                
            print(f"Updated/Inserted prod inflation data for: {last_month_data.producto.unique()} {last_month_data['fecha'].min()} to {last_month_data['fecha'].max()}")
        else:
            # There are no new records to update, so skip this product
            print("No data to update")
    else:
        # No existing records, insert all new records
        collection.insert_many(all_data.to_dict(orient='records'))
        print("initial ingestion")
        print(f"Updated/Inserted prod inflation data for {all_data['fecha'].min()} to {all_data['fecha'].max()}")
        print(f"Ingesting data: {all_data.shape}")

    return all_data

def calcCategoriesInflation(inflations_product: pd.DataFrame, sector: str) -> pd.DataFrame:
    """
    Calculate inflation for each category in the given sector.

    The function calculates the inflation for each category in the given sector
    based on the daily inflation percentages of its products.

    Args:
        inflations_product (pd.DataFrame): DataFrame containing inflation data
                                           with columns 'fecha', 'inflation', and 'category'.
        sector (str): The sector name for which inflation needs to be calculated.

    Returns:
        pd.DataFrame: DataFrame containing category-wise inflation data with columns 'fecha',
                      'inflation', and 'category'.
    """
    pesos = {
            'alimentacion': [   0.05882, # Aceite
                0.05882, # mantequilla
                0.05882, # arroz
                0.05882, # maiz
                0.05882, # garbanzos
                0.05882, # alubias
                0.05882, # patata
                0.05882, # azucar
                0.05882, # pescado
                0.05882, # huevos
                0.05882, # pollo
                0.05882, # leche
                0.05882, # agua
                0.05882, # cafe
                0.05882, # cerveza
                0.05882, # platano
                0.05882, # manzana
            ],
            'energia': [   
                0.1, # Sin Plomo 95
                0.1, # Sin Plomo 98
                0.1, # Gasóleo A
                0.1, # Gasóleo A+
                0.1, # Gasóleo B
                0.1, # Gasóleo C
                0.1, # Biodiésel
                0.1, # Autogas/GLP
                0.1, # GNC
                0.1 # Luz
            ],
            'vivienda': [
                0.5, # Venta
                0.5 # Alquiler
            ],
        }
    
    categ_inflations = []
    for date in inflations_product.fecha.unique():
        daily_inflations = inflations_product[inflations_product['fecha'] == date]['inflation'].values

        
        inflationCategory_pct = []
        for num1, num2 in zip(daily_inflations, pesos[sector]):
            inflationCategory_pct.append(num1 * num2)
        inflationCategory= sum(inflationCategory_pct)

        categ_inflations.append({'fecha':date, 'inflation':inflationCategory , 'category': sector})
    
    categ_inflations = pd.DataFrame.from_records(categ_inflations)

    return categ_inflations


def update_categories_inflations():
    # MongoDB configuration
    myclient = pymongo.MongoClient(st.secrets["DB_SECRET"])
    mydb = myclient[DATABASE]

    # Fetch data from MongoDB collection "yearly_inflation_prod"
    yearly_inflation_prod_data = pd.json_normalize(list(mydb["YoY_inflation_per_prod"].find()))

    # Convert 'fecha' column to datetime
    yearly_inflation_prod_data['fecha'] = pd.to_datetime(yearly_inflation_prod_data['fecha'])

    # Group data by 'category'
    grouped_data = yearly_inflation_prod_data.groupby('sector')

    latest_record = mydb["YoY_inflation_category"].find_one({}, sort=[('fecha', pymongo.DESCENDING)])
    for sector, data in grouped_data:
        # Check if it is the first run or subsequent run
        sector_inflation = calcCategoriesInflation(data, sector)
        data_columns = sector_inflation.columns.tolist()
        
        if latest_record:
            last_month = latest_record['fecha'].replace(day=1)
            last_month_data = sector_inflation[sector_inflation['fecha'] >= last_month]
            
            # Check if there are any records to update for the last month
            if not last_month_data.empty:
                # Update the existing records for the last month
                for _, record in last_month_data.iterrows():
                    filter_dict = {col: record[col] for col in data_columns if col != 'inflation'}
                    mydb["YoY_inflation_category"].update_one(filter_dict, {'$set': {'inflation': record['inflation']}}, upsert=True)
                print(f"Updated/Inserted {sector} category inflation data for {last_month_data['fecha'].min()} to {last_month_data['fecha'].max()}")
            else:
                # There are no new records to update, so skip this product
                print("No data to update")
        else:
            # No existing records, insert all new records
            mydb["YoY_inflation_category"].insert_many(sector_inflation.to_dict(orient='records'))
            print("initial ingestion")
            print(f"Ingesting data: {sector_inflation.shape}")
            print(f"Updated/Inserted {sector} category inflation data for {sector_inflation['fecha'].min()} to {sector_inflation['fecha'].max()}")

        


def calcTotalInflation(inflations_categ: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate total inflation for each date based on category-wise inflations.

    The function calculates the total inflation for each date by aggregating the inflation
    percentages of different categories based on their weights.

    Args:
        inflations_categ (pd.DataFrame): DataFrame containing category-wise inflation data
                                         with columns 'fecha', 'inflation', and 'category'.

    Returns:
        pd.DataFrame: DataFrame containing total inflation data with columns 'fecha',
                      'inflation', and 'category' set to 'total'.
    """
    pesos = [
            0.33, # Alimentacion
            0.33, # Energia
            0.33  # Vivienda
        ]
    
    total_inflations = []
    for date in inflations_categ.fecha.unique():
        daily_inflations = inflations_categ[(inflations_categ['fecha'] == date) & (inflations_categ['category'] != 'total')]['inflation'].values

        inflationCategory_pct = []
        for num1, num2 in zip(daily_inflations, pesos):
            inflationCategory_pct.append(num1 * num2)
        inflationCategory= sum(inflationCategory_pct)
        total_inflations.append({'fecha':date, 'inflation':inflationCategory , 'category': 'total'})
    
    total_inflations = pd.DataFrame.from_records(total_inflations)

    return total_inflations

def update_total_inflations():
    # MongoDB configuration
    myclient = pymongo.MongoClient(st.secrets["DB_SECRET"])
    mydb = myclient[DATABASE]

    # Fetch data from MongoDB collection "yearly_inflation_prod"
    yearly_inflation_categories = pd.json_normalize(list(mydb["YoY_inflation_category"].find()))

    # Convert 'fecha' column to datetime
    yearly_inflation_categories['fecha'] = pd.to_datetime(yearly_inflation_categories['fecha'])

    latest_record = mydb["YoY_inflation_category"].find_one({"category": "total"}, sort=[('fecha', pymongo.DESCENDING)])

    # Check if it is the first run or subsequent run
    total_inflation = calcTotalInflation(yearly_inflation_categories)
    data_columns = total_inflation.columns.tolist()
    
    if latest_record:
        last_month = latest_record['fecha'].replace(day=1)
        last_month_data = total_inflation[total_inflation['fecha'] >= last_month]
        
        # Check if there are any records to update for the last month
        if not last_month_data.empty:
            # Update the existing records for the last month
            for _, record in last_month_data.iterrows():
                filter_dict = {col: record[col] for col in data_columns if col != 'inflation'}
                mydb["YoY_inflation_category"].update_one(filter_dict, {'$set': {'inflation': record['inflation']}}, upsert=True)
            print(f"Updated/Inserted Chainflation Index data for {last_month_data['fecha'].min()} to {last_month_data['fecha'].max()}")
        else:
            # There are no new records to update, so skip this product
            print("No data to update")
    else:
        # No existing records, insert all new records
        mydb["YoY_inflation_category"].insert_many(total_inflation.to_dict(orient='records'))
        print("initial ingestion")
        print(f"Ingesting data: {total_inflation.shape}")
        print(f"Updated/Inserted Chainflation Index data for {total_inflation['fecha'].min()} to {total_inflation['fecha'].max()}")


########### MONGODB GETTERS ################

def getMonthlyProductPrices():
    # Read data from MongoDB collections
    myclient = pymongo.MongoClient(st.secrets["DB_SECRET"])
    mydb = myclient[DATABASE]

    vivienda_monthly = pd.json_normalize(list(mydb["vivienda_monthly"].find()))
    alimentacion_monthly = pd.json_normalize(list(mydb["alimentacion_monthly"].find()))
    energia_monthly = pd.json_normalize(list(mydb["energia_monthly"].find()))


    # Convert 'fecha' column to datetime
    vivienda_monthly['fecha'] = pd.to_datetime(vivienda_monthly['fecha'])
    alimentacion_monthly['fecha'] = pd.to_datetime(alimentacion_monthly['fecha'])
    energia_monthly['fecha'] = pd.to_datetime(energia_monthly['fecha'])

    monthly_prod_prices = {
        'vivienda': vivienda_monthly,
        'alimentacion':alimentacion_monthly,
        'energia': energia_monthly,
    }

    return monthly_prod_prices

def getProductInflation(include_source=False) -> Dict[str, pd.DataFrame]:
    """
    Get inflation for each product in the given sector.

    Args:
        sector_df (Dict[str, pd.DataFrame]): A dictionary containing DataFrames with product prices
                                             for 'energia', 'vivienda', and 'alimentacion' sectors.
        ago (int): Number of days to compare the prices with.

    Returns:
        Dict[str, pd.DataFrame]: A dictionary containing DataFrames with inflation data for each product
                                 in the 'energia', 'vivienda', and 'alimentacion' sectors.
    """

    # Read data from MongoDB collections
    myclient = pymongo.MongoClient(st.secrets["DB_SECRET"])
    mydb = myclient[DATABASE]
    
    if include_source:
        collection = "YoY_inflation_per_prod_source"
    else:
        collection = "YoY_inflation_per_prod"
    # Fetch data from MongoDB collections for 'energia', 'vivienda', and 'alimentacion' sectors
    YoY_inflation_per_prod_df  = pd.json_normalize(list(mydb[collection].find()))

    return YoY_inflation_per_prod_df

def getCategoriesInflation() -> Dict[str, pd.DataFrame]:
    """
    Calculate inflation for each category in the given sectors.

    Args:
        sector_df (Dict[str, pd.DataFrame]): A dictionary containing DataFrames with product prices
                                             for 'energia', 'vivienda', and 'alimentacion' sectors.

    Returns:
        Dict[str, pd.DataFrame]: A dictionary containing DataFrames with inflation data for each category
                                 in the 'energia', 'vivienda', and 'alimentacion' sectors.
    """
    
    # Read data from MongoDB collections
    myclient = pymongo.MongoClient(st.secrets["DB_SECRET"])
    mydb = myclient[DATABASE]
    
    collection = "YoY_inflation_category"

    YoY_inflation_category_df  = pd.json_normalize(list(mydb[collection].find()))
    return YoY_inflation_category_df
