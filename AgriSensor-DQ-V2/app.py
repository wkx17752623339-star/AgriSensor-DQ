import streamlit as st
from engine import demo_data,detect,normalize
import pandas as pd
from pathlib import Path
import os
from ui.theme import apply
from services.storage import init
from services.workflow import get_active_dataset, load_dataset
from pages_ui import dashboard,nodes,data_manager,diagnosis,quality_page,experiments,reports
st.set_page_config(page_title='AgriSensor-DQ | 智慧农业传感器平台',page_icon='🌱',layout='wide',initial_sidebar_state='expanded')
apply();init()
CLOUD_DEMO = os.getenv('AGRISENSOR_CLOUD_DEMO', '1') == '1'
if 'dataset' not in st.session_state:
 if CLOUD_DEMO:
  sample = Path(__file__).resolve().parent / 'data' / 'processed' / 'greenhouse_sample.csv'
  if sample.is_file():
   st.session_state.dataset = pd.read_csv(sample)
   st.session_state.source = '真实温室公开样本（CSV）'
  else:
   st.session_state.dataset = demo_data()
   st.session_state.source = '模拟数据（示例文件缺失）'
 else:
  active_id = get_active_dataset()
  if active_id:
   try:
    st.session_state.dataset = load_dataset(active_id)
    st.session_state.dataset_id = active_id
    st.session_state.source = '已恢复的数据集 ' + active_id
   except (FileNotFoundError, ValueError, KeyError) as exc:
    st.warning('上次数据集恢复失败，已临时使用模拟数据：' + str(exc))
    st.session_state.dataset = demo_data()
    st.session_state.source = '模拟数据（恢复失败）'
  else:
   st.session_state.dataset = demo_data()
   st.session_state.source = '模拟数据'
if 'method' not in st.session_state:st.session_state.method='Hampel'
df=normalize(st.session_state.dataset)
with st.sidebar:
 st.markdown('## 🌱 AgriSensor-DQ')
 st.caption('农业无线传感器网络 · 数据质量与故障诊断')
 st.divider()
 menu=st.radio('功能导航',['🏠 系统总览','📡 节点监控','🗂️ 数据管理','🛠️ 故障诊断','🧬 质量评价','📊 算法实验','📑 报告导出'],label_visibility='collapsed')
 st.divider()
 st.caption('数据来源：'+st.session_state.source)
 st.caption(f'节点数：{df.node_id.nunique()}  ·  记录：{len(df):,}')
 st.info('云端演示：真实温室样本与上传数据均可分析；无真实硬件连接。上传和实验结果不保证跨重启保存。' if CLOUD_DEMO else '本地演示：无真实硬件连接。')
try:
 det=detect(df,method=st.session_state.method)
 if menu.startswith('🏠'):dashboard.render(df,det)
 elif menu.startswith('📡'):nodes.render(df,det)
 elif menu.startswith('🗂️'):data_manager.render(df)
 elif menu.startswith('🛠️'):diagnosis.render(df)
 elif menu.startswith('🧬'):quality_page.render(df,det)
 elif menu.startswith('📊'):experiments.render(df)
 else:reports.render(df,det)
except Exception as e:
 st.error('页面运行失败：'+str(e));st.exception(e)
