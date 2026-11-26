import pandas as pd
import streamlit as st
import plotly.express as px
import numpy as np

THRESHOLDS=[250000,300000,400000,500000,600000,750000,1000000,1500000,2000000]
GENERAL=[1,1.5,2,2.5,3,3.5,4,4.5,5]
ELECTRICAL=[1,1.5,2,2.5,3,3,3.5,4,5]
PLUMBING=[1.5,2,2.5,3,3.5,4,4.5,5,5]
COLS=[f'${n:,}+' for n in THRESHOLDS]
KEYS=['Supplier label','Trade category']
def default_matrix(trades):
    rows=[]
    for trade in sorted(trades):
        label=trade.casefold().strip()
        if label=='plumbing': rates=PLUMBING
        elif label in ('electrical','hvac','cranage'): rates=ELECTRICAL
        elif label in ('carpentry','other modular works (review)','other modular works','get ready / units maint','get ready / units maintenance','vinyl / carpet laying','painting','cleaning of modules','welding','metalworker, locksmith','metalworker / locksmith'): rates=GENERAL
        else: rates=[0]*9
        rows.append([trade,*rates])
    return pd.DataFrame(rows,columns=['Trade category',*COLS])

def calculate(national,visible,matrix,thresholds):
    rates=matrix.set_index('Trade category')
    annual=national.groupby(KEYS,dropna=False).Amount.sum().reset_index(name='National annual spend')
    def tier(r):
        i=np.searchsorted(thresholds,r['National annual spend'],side='right')-1
        return float(rates.loc[r['Trade category'],COLS[i]])/100 if i>=0 and r['Trade category'] in rates.index else 0.
    annual['Rebate rate']=annual.apply(tier,axis=1) if len(annual) else pd.Series(dtype=float)
    # Allocate the national supplier/trade rebate to the filtered spend. No re-tiering by location.
    annual['National potential rebate']=annual['National annual spend']*annual['Rebate rate']
    details=visible.merge(annual,on=KEYS,how='left',validate='many_to_one')
    details['Potential rebate']=details.Amount*details['Rebate rate'].fillna(0)
    details['Eligible net spend']=details.Amount.where(details['Rebate rate'].gt(0),0)
    return annual,details

def summarize(details,dims):
    out=details.groupby(dims,dropna=False).agg(**{'Net spend':('Amount','sum'),'Eligible net spend':('Eligible net spend','sum'),'Potential rebate':('Potential rebate','sum'),'Suppliers':('Supplier label','nunique')}).reset_index()
    out['Effective rebate rate']=np.divide(out['Potential rebate'],out['Net spend'],out=np.zeros(len(out)),where=out['Net spend'].to_numpy()>0)
    return out.sort_values('Potential rebate',ascending=False)

def render_rebate(d,national,key,display_table,csv):
    st.subheader('Rebate opportunity analysis')
    st.caption('Proposed negotiation targets, not contracted savings. Annual retrospective rebates by supplier entity and trade, calculated nationally and allocated to filtered spend. Credits retained; GST excluded; no additional eligibility exclusions assumed.')
    from datetime import date
    c1,c2=st.columns(2)
    start=pd.Timestamp(c1.date_input('Baseline start (inclusive)',date(2025,1,1)))
    end=pd.Timestamp(c2.date_input('Baseline end (exclusive)',date(2026,1,1)))
    if end<=start: st.error('End date must follow start date.'); return
    n=national[national['Posting Date'].ge(start)&national['Posting Date'].lt(end)]
    q=d[d['Posting Date'].ge(start)&d['Posting Date'].lt(end)]
    if end!=start+pd.DateOffset(years=1): st.warning('Selected period is not one year. Actual spend is used without annualisation.')
    if national['Posting Date'].min()>start or national['Posting Date'].max()<end-pd.Timedelta(days=1): st.warning('Source coverage may be incomplete for this baseline. Actual spend only.')
    st.caption('Sidebar state, facility, trade, supplier and description filters change reporting, not national annual spend used to qualify for tiers. Baseline dates are inclusive start and exclusive end.')
    trades=tuple(sorted(national['Trade category'].dropna().unique())); statekey='rebates-'+key+'-'+str(trades)
    if statekey not in st.session_state: st.session_state[statekey]=(default_matrix(trades),THRESHOLDS.copy(),0)
    matrix,thresholds,version=st.session_state[statekey]
    with st.expander('Editable rebate matrix and spend thresholds',expanded=True):
        st.caption('Enter rates as percentage points (e.g. 2.5 means 2.5%). Below the first tier the rate is zero. Edit thresholds and rates, then Apply to recalculate.')
        with st.form('rebate-edit-'+str(version)):
            cols=st.columns(3); proposed=[cols[i%3].number_input(f'Tier {i+1} annual spend ($)',min_value=1,value=int(t),step=25000,key=f'tier-{version}-{i}') for i,t in enumerate(thresholds)]
            config={'Trade category':st.column_config.TextColumn(disabled=True)}
            config.update({c:st.column_config.NumberColumn(label=f'${thresholds[i]:,}+ (%)',min_value=0.,max_value=100.,step=.5,format='%.2f',alignment='center') for i,c in enumerate(COLS)})
            edited=st.data_editor(matrix,key=f'rebate-matrix-{version}',column_config=config,hide_index=True,use_container_width=True,disabled=['Trade category'])
            apply=st.form_submit_button('Apply rebate schedule')
        if apply:
            vals=edited[COLS].apply(pd.to_numeric,errors='coerce')
            if any(a>=b for a,b in zip(proposed,proposed[1:])) or vals.isna().any().any() or (vals<0).any().any() or (vals>100).any().any() or (vals.diff(axis=1).iloc[:,1:]<0).any().any(): st.error('Thresholds must strictly increase; rates must be complete, 0–100%, and non-decreasing.')
            else: st.session_state[statekey]=(edited,proposed,version+1); st.rerun()
        export=matrix.rename(columns=dict(zip(COLS,[str(t) for t in thresholds])))
        st.download_button('Export rebate schedule',csv(export),'rebate_schedule.csv')
        restore=st.file_uploader('Restore a previously exported rebate schedule',type=['csv'],key='rebate-restore')
        if st.button('Restore schedule'):
            try:
                restored=pd.read_csv(restore); th=[int(c) for c in restored.columns[1:]]; vals=restored.iloc[:,1:].apply(pd.to_numeric,errors='raise')
                if restored.columns[0]!='Trade category' or len(th)!=9 or min(th)<=0 or any(a>=b for a,b in zip(th,th[1:])) or restored['Trade category'].duplicated().any() or set(restored['Trade category'])!=set(trades) or vals.isna().any().any() or (vals<0).any().any() or (vals>100).any().any() or (vals.diff(axis=1).iloc[:,1:]<0).any().any(): raise ValueError()
                restored.columns=['Trade category',*COLS]; st.session_state[statekey]=(restored,th,version+1); st.rerun()
            except Exception: st.error('Invalid schedule. Use the exported CSV with all current trades and nine valid tiers.')
        if st.button('Reset to proposed defaults'): st.session_state[statekey]=(default_matrix(trades),THRESHOLDS.copy(),version+1); st.rerun()
        st.caption('Edits are session-only; export the schedule to reuse later.')
    annual,details=calculate(n,q,matrix,thresholds)
    if details.empty: st.info('No transactions match the selected baseline and filters.'); return
    total=details.Amount.sum(); rebate=details['Potential rebate'].sum(); eligible=details['Eligible net spend'].sum()
    k=st.columns(4); k[0].metric('Filtered net spend',f'${total:,.0f}'); k[1].metric('Eligible net spend',f'${eligible:,.0f}'); k[2].metric('Potential rebate',f'${rebate:,.0f}'); k[3].metric('Effective rebate rate',f'{rebate/total:.2%}' if total>0 else 'N/A')
    dims=st.radio('View rebate opportunity by',['Supplier','Trade','State','Facility','Supplier and trade','State and trade'],horizontal=True)
    group={'Supplier':['Supplier label'],'Trade':['Trade category'],'State':['State'],'Facility':['Facility'],'Supplier and trade':KEYS,'State and trade':['State','Trade category']}[dims]
    out=summarize(details,group)
    def show(frame):
        config={c:st.column_config.NumberColumn(format='percent' if 'rate' in c.lower() else 'localized',alignment='center') for c in frame.select_dtypes(include='number').columns}
        st.dataframe(frame,column_config=config,hide_index=True,use_container_width=True)
    show(out); st.download_button('Export rebate analysis',csv(out),'rebate_analysis.csv')
    chart=out.head(20).copy(); chart['Group']=chart[group].astype(str).agg(' | '.join,axis=1)
    st.plotly_chart(px.bar(chart.sort_values('Potential rebate'),x='Potential rebate',y='Group',orientation='h',title='Top rebate opportunities',template='plotly_white',color_discrete_sequence=['#167D83']),use_container_width=True)
    st.subheader('Supplier / trade tier detail')
    detail=summarize(details,KEYS).merge(annual,on=KEYS,validate='one_to_one')
    detail['Next tier spend gap']=detail.apply(lambda r: next((t-r['National annual spend'] for i,t in enumerate(thresholds) if t>r['National annual spend'] and matrix.set_index('Trade category').loc[r['Trade category'],COLS[i]]/100>r['Rebate rate']),float('nan')),axis=1)
    show(detail); st.download_button('Export supplier tier detail',csv(detail),'supplier_rebate_detail.csv')
