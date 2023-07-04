import pandas as pd
import pickle

def to_excel(input_file: str, output_file: str) -> None:
    df = pd.DataFrame(columns=['id', 'username', 'product', 'province', 'city', 'village','area', 'phone', 'latitude', 'longitude', 'name', 'blocked'])
    
    with open(input_file, 'rb') as f:
        user_data = pickle.load(f)["user_data"]
    
    for i, key in enumerate(user_data):
        location = user_data.get(key, {}).get('location')
        if location:
            latitude = location['latitude']
            longitude = location['longitude']
        else:
            latitude = None
            longitude = None
        df.loc[i] = pd.Series({
            'id': key,
            'username': user_data.get(key, {}).get('username'),
            'product': user_data.get(key, {}).get('produce'),
            'province': user_data.get(key, {}).get('province'),
            'city': user_data.get(key, {}).get('city'),
            'village': user_data.get(key, {}).get('village'),
            'area': user_data.get(key, {}).get('area'),
            'phone': user_data.get(key, {}).get('phone'),
            'latitude': latitude,
            'longitude': longitude,
            'name': user_data.get(key, {}).get('name'),
            'blocked': user_data.get(key, {}).get('blocked'),
        })
    
    df.to_excel(output_file)
