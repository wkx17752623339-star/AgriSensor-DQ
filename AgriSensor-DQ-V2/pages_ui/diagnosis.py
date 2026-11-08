"""Isolated synthetic-fault experiments; never overwrite the active raw dataset."""
import hashlib
import json
import time
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from ui.theme import heading
from engine import detect, evaluate
from services.faults import inject, KINDS
from services.storage import log
from services.workflow import save_dataset, save_run
from services.data_io import csv_bytes


def fingerprint(df):
    cols = [c for c in ('timestamp','node_id','temperature','humidity','rssi','snr','fault_type','is_fault') if c in df.columns]
    h = pd.util.hash_pandas_object(df[cols].reset_index(drop=True), index=False).values
    return hashlib.sha256(h.tobytes()).hexdigest()


def render(df):
    heading('故障诊断工作台', '原始数据保护 → 独立实验副本 → 故障检测 → 结果保存')
    baseline_sig = fingerprint(df)
    if st.session_state.get('dq_baseline_sig') != baseline_sig:
        for key in ('dq_experiment_df','dq_injected_mask','dq_result','dq_run_key','dq_injection_info'):
            st.session_state.pop(key, None)
        st.session_state.dq_baseline_sig = baseline_sig
    st.success('当前原始数据保持不变；本页面注入故障只修改实验副本。')
    node = st.selectbox('目标节点', sorted(df.node_id.astype(str).unique()), key='fault_node')
    a,b,c = st.columns(3)
    kind = a.selectbox('故障类型', KINDS)
    field = b.selectbox('故障字段', ['temperature','humidity','rssi'])
    strength = c.slider('故障强度',1.0,25.0,8.0)
    a,b,c = st.columns(3)
    start = a.slider('故障开始位置（%）',0,90,30)
    duration = b.slider('持续长度（%）',2,50,12)
    seed = int(c.number_input('故障随机种子',0,999999,21))
    left,right = st.columns(2)
    if left.button('从原始数据创建故障实验副本',type='primary'):
        try:
            # Always inject into a fresh copy, never stack faults on prior experiments.
            work = inject(df.copy(), node, kind, strength, seed, start/100, duration/100, field)
            # The injection function labels affected rows via fault_type, without
            # falsely labelling unverified original observations as normal.
            mask = work['fault_type'].eq(kind) & work['node_id'].eq(node)
            st.session_state.dq_experiment_df = work
            st.session_state.dq_injected_mask = mask
            st.session_state.dq_injection_info = dict(node=node,kind=kind,field=field,strength=strength,start=start,duration=duration,seed=seed,inserted=int(mask.sum()))
            st.session_state.pop('dq_result',None)
            st.session_state.pop('dq_run_key',None)
            log(node,kind,f'isolated; {field}; strength={strength}; start={start}%; duration={duration}%; seed={seed}')
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if right.button('清除实验副本（恢复原始视图）'):
        for key in ('dq_experiment_df','dq_injected_mask','dq_result','dq_run_key','dq_injection_info'):
            st.session_state.pop(key,None)
        st.rerun()
    work = st.session_state.get('dq_experiment_df')
    if work is None:
        st.info('当前分析原始数据。可直接运行检测，或先创建实验副本。')
        work = df
    else:
        info = st.session_state['dq_injection_info']
        st.info(f"实验副本：{info['node']} / {info['kind']} / {info['field']}，注入记录 {info['inserted']} 条。原始数据未改变。")
        old = df[df.node_id.eq(node)]
        new = work[work.node_id.eq(node)]
        if len(old)==len(new):
            fig=go.Figure()
            fig.add_scatter(x=old.timestamp,y=old[field],name='原始',mode='lines')
            fig.add_scatter(x=new.timestamp,y=new[field],name='实验副本',mode='lines')
            fig.update_layout(height=320,title='故障注入前后对比')
            st.plotly_chart(fig,use_container_width=True)
    st.divider()
    st.subheader('运行故障检测')
    method=st.selectbox('检测算法',['Hampel','Isolation Forest','阈值法'])
    window=st.slider('Hampel窗口',5,31,11,step=2)
    threshold=st.slider('Hampel敏感度',1.5,6.0,3.0,step=.5)
    contamination=st.slider('Isolation Forest异常比例',.01,.30,.08,step=.01)
    params=dict(method=method,window=window,threshold=threshold,contamination=contamination)
    run_key=(fingerprint(work),json.dumps(params,sort_keys=True))
    if st.button('运行检测算法'):
        t0=time.perf_counter()
        st.session_state.dq_result=detect(work,**params)
        st.session_state.dq_runtime=round(time.perf_counter()-t0,4)
        st.session_state.dq_run_key=run_key
    result=st.session_state.get('dq_result')
    if result is None or st.session_state.get('dq_run_key') != run_key:
        st.info('请点击“运行检测算法”生成当前实验的诊断结果。')
        return
    st.metric('本次检测耗时（秒）',st.session_state.get('dq_runtime',0))
    st.metric('全部节点检测异常记录数',int(result.detected_fault.sum()))
    # Do not evaluate synthetic injections against unverified real-world negatives.
    # Only evaluate if an independently supplied, fully verified truth column exists.
    score=evaluate(result)
    if score:
        a,b,c=st.columns(3)
        a.metric('Precision',f"{score['Precision']:.3f}")
        b.metric('Recall',f"{score['Recall']:.3f}")
        c.metric('F1',f"{score['F1']:.3f}")
        st.caption('以上指标仅基于数据中已提供的非空真值标签。')
    else:
        st.warning('真实原始数据缺少经过核实的完整真值标签，不能计算可信的Precision/Recall/F1。人工注入位置可用于检测命中分析，但不能将其他真实观测直接视为正常。')
    mask=st.session_state.get('dq_injected_mask')
    if mask is not None:
        hits=int((result['detected_fault'].eq(1) & mask).sum())
        total=int(mask.sum())
        st.metric('已注入故障点被检出',f'{hits} / {total}')
        st.caption('这是人工注入点命中率，不是完整Recall；原始数据可能存在未知异常。')
    g=result[result.node_id.eq(node)]
    fig=go.Figure()
    fig.add_scatter(x=g.timestamp,y=g[field],name='测量值',mode='lines')
    bad=g[g.detected_fault.eq(1)]
    fig.add_scatter(x=bad.timestamp,y=bad[field],name='检测异常',mode='markers',marker=dict(color='#df584d',size=8))
    fig.update_layout(height=380,title='异常检测结果')
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(bad.head(200),use_container_width=True,hide_index=True)
    if st.button('保存本次诊断实验'):
        did=save_dataset(work,'诊断实验数据',st.session_state.get('source','未知'))
        metrics=score or {'verified_ground_truth':False,'detected':int(result.detected_fault.sum())}
        metrics['runtime_seconds']=st.session_state.get('dq_runtime',0)
        if mask is not None:
            metrics.update(injected_count=int(mask.sum()),injected_hits=int((result.detected_fault.eq(1)&mask).sum()))
        rid=save_run(did,method,{**params,'node':node,'injection':st.session_state.get('dq_injection_info')},metrics)
        st.success(f'实验 #{rid} 已保存，可在报告导出页查看。')
    st.download_button('下载检测明细CSV',csv_bytes(result),'diagnosis_results.csv','text/csv')
