from io import BytesIO
import pandas as pd
from engine import normalize

def read_upload(file):
 name=file.name.lower()
 if name.endswith('.csv'):
  raw=file.getvalue(); last=None
  for enc in ('utf-8-sig','gb18030'):
   try:return normalize(pd.read_csv(BytesIO(raw),encoding=enc))
   except UnicodeDecodeError as e:last=e
  raise ValueError(f'CSV编码错误: {last}')
 if name.endswith(('.xlsx','.xls')):return normalize(pd.read_excel(BytesIO(file.getvalue())))
 raise ValueError('仅支持 CSV / XLSX / XLS')

def csv_bytes(df):return df.to_csv(index=False).encode('utf-8-sig')
