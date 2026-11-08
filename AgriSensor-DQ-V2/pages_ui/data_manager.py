import os
from pathlib import Path
import pandas as pd
import streamlit as st
from ui.theme import heading
from services.data_io import read_upload,csv_bytes
from services.workflow import save_dataset,load_dataset,list_datasets,set_active_dataset,clear_active_dataset
from engine import demo_data

def render(df):
    cloud = os.getenv('AGRISENSOR_CLOUD_DEMO', '1') == '1'
    heading('数据管理中心','导入、生成与查看传感器数据集' if cloud else '导入、生成、持久化与恢复传感器数据集')
    if cloud: st.warning('云端演示模式：上传数据只在当前浏览器会话中使用；请下载结果保存。重启或休眠后数据可能丢失。')
    st.info('必需字段：timestamp、node_id、temperature、humidity；rssi、fault_type、is_fault可选。无真实标签时不计算监督评价。')
    f=st.file_uploader('上传CSV或Excel',type=['csv','xlsx','xls'])
    if f is not None and st.button('导入并应用',type='primary'):
        try:
            d=read_upload(f)
            did = None if cloud else save_dataset(d, f.name, f.name)
            if not cloud: set_active_dataset(did)
            st.session_state.dataset=d;st.session_state.source=f.name
            if did: st.session_state.dataset_id=did
            st.session_state.pop('experiment',None);st.success('导入成功');st.rerun()
        except Exception as e:st.error(str(e))
    a,b,c=st.columns(3)
    nodes=a.slider('模拟节点数',2,20,8);days=b.slider('模拟天数',1,14,3);seed=c.number_input('随机种子',0,99999,42)
    if st.button('重新生成模拟数据'):
        st.session_state.dataset=demo_data(nodes=nodes,days=days,seed=int(seed));st.session_state.source='模拟数据'
        st.session_state.pop('dataset_id',None)
        if not cloud: clear_active_dataset()
        st.session_state.pop('experiment',None);st.rerun()
    if cloud:
        st.subheader('当前数据预览');st.dataframe(df.head(250),use_container_width=True,hide_index=True)
        st.download_button('下载当前CSV',csv_bytes(df),'agrisensor_data.csv','text/csv')
        return
    st.divider();st.subheader('数据集持久化')
    name=st.text_input('保存名称',value='温室传感器数据集')
    if st.button('保存当前数据到本地数据库'):
        did=save_dataset(df,name,st.session_state.get('source','未知'))
        st.session_state.dataset_id=did;set_active_dataset(did);st.success(f'已保存，数据集ID：{did}')
    catalog=list_datasets()
    if not catalog.empty:
        st.dataframe(catalog,use_container_width=True,hide_index=True)
        selected=st.selectbox('选择历史数据集',catalog['id'].tolist(),format_func=lambda v:catalog.set_index('id').loc[v,'name']+' · '+v)
        if st.button('加载所选数据集'):
            st.session_state.dataset=load_dataset(selected);st.session_state.dataset_id=selected
            set_active_dataset(selected)
            st.session_state.source='已保存数据集 '+selected;st.session_state.pop('experiment',None);st.rerun()
    st.subheader('当前数据预览');st.dataframe(df.head(250),use_container_width=True,hide_index=True)
    st.download_button('下载当前CSV',csv_bytes(df),'agrisensor_data.csv','text/csv')
