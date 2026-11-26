import io, re, hashlib, hmac, time
from pathlib import Path
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
st.set_page_config(page_title='Ausco Procurement Analytics',layout='wide')
st.markdown('''<style>.block-container{padding-top:2rem} [data-testid="stMetric"]{background:rgba(120,140,150,.08);padding:16px;border-radius:8px} </style>''',unsafe_allow_html=True)
st.title('Ausco Procurement Analytics')
def secret(name, default=''):
    try: return st.secrets.get(name, default)
    except FileNotFoundError: return default

def login():
    expected = secret('APP_PASSWORD')
    if not expected:
        st.error('Administrator must configure APP_PASSWORD in Streamlit Secrets.'); st.stop()
    if not st.session_state.get('authenticated'):
        st.caption('Authorised access only')
        with st.form('login'):
            password = st.text_input('Password', type='password')
            submitted = st.form_submit_button('Sign in')
        if submitted:
            if hmac.compare_digest(password.encode(), str(expected).encode()):
                st.session_state.authenticated = True; st.rerun()
            else:
                time.sleep(2); st.error('Incorrect password.')
        st.stop()
    if st.sidebar.button('Sign out'):
        st.session_state.clear(); st.rerun()
login()
st.caption('Spend intelligence • Supplier strategy • Manufacturing network')

def numeric_config(df):
    config = {}
    for c in df.select_dtypes(include='number').columns:
        name = str(c)
        fmt = 'percent' if 'share' in name.lower() else 'localized'
        config[c] = st.column_config.NumberColumn(format=fmt, alignment='center')
    return config

def display_table(df, **kwargs):
    st.dataframe(df, column_config=numeric_config(df), **kwargs)

U='Unmapped'
def clean(s): return s.fillna('').astype(str).str.strip().str.replace(r'\.0$','',regex=True)
@st.cache_data
def load(raw,name):
    if name.lower().endswith('.csv'):
        x=pd.read_csv(io.BytesIO(raw))
    else:
        preview=pd.read_excel(io.BytesIO(raw),header=None,nrows=30)
        hits=preview.index[preview.apply(lambda r: {'Posting Date','Vendor No.','Amount'}.issubset(set(r.astype(str).str.strip())),axis=1)]
        if not len(hits): raise ValueError('Cannot locate transaction headers in first 30 rows.')
        x=pd.read_excel(io.BytesIO(raw),header=int(hits[0]))
    x.columns=x.columns.str.strip()
    required=['Posting Date','Vendor No.','Vendor Name','Amount','Branch','Branch Code','Trade']
    if missing:=set(required)-set(x.columns): raise ValueError(f'Missing columns: {missing}')
    x=x.dropna(how='all').copy(); x['Source row']=range(1,len(x)+1)
    x['Posting Date']=pd.to_datetime(x['Posting Date'],errors='coerce'); x['Amount']=pd.to_numeric(x['Amount'],errors='coerce')
    for c in ['Vendor No.','Vendor Name','ABN','Branch','Branch Code','Trade','Description','Description 2','Document No.','Order No.','Department Code','Payment Terms','Blocked Vendor']:
        if c not in x: x[c]=''
        x[c]=clean(x[c])
    return x

def mappings(x):
    v=x.groupby('Vendor No.',dropna=False).agg(**{'Vendor Name':('Vendor Name','first'),'ABN':('ABN','first'),'Name variants':('Vendor Name','nunique'),'ABN variants':('ABN','nunique')}).reset_index()
    valid=v.ABN.str.fullmatch(r'\d{11}') & ~v.ABN.eq('00000000000') & v['ABN variants'].eq(1)
    v['Entity ID']='Vendor:'+v['Vendor No.']; v.loc[valid,'Entity ID']='ABN:'+v.loc[valid,'ABN']
    v['Supplier']=v.groupby('Entity ID')['Vendor Name'].transform('first'); v['Vendor type']='Subcontractor (source scope)'
    b=x[['Branch Code','Branch']].drop_duplicates().copy()
    def state(r):
        c=r['Branch Code']; n=r.Branch
        if n=='Canberra': return 'ACT'
        if n=='Launceston': return 'TAS'
        if n=='Darwin': return 'NT'
        if n in ['NSW/ACT Sale','VIC/TAS Sale','SA/NT Sale']: return n.split(' ')[0]
        if c in ['104','105']: return 'QLD'
        if c=='106': return 'SA'
        if c=='107': return 'WA'
        return {'2':'NSW','3':'VIC','4':'QLD','5':'SA','6':'WA'}.get(c[:1],'National / review')
    b['State']=b.apply(state,axis=1); b['Facility type']=b.Branch.map(lambda n:'Manufacturing' if 'Factory' in n else 'Other / review'); b['Facility']=b.Branch
    t=x[['Trade']].drop_duplicates().copy(); t['Trade category']=t.Trade.str.replace(r'^SUBCONTRACTING - |^SUBCONTRATING - ','',regex=True).str.title().replace({'Electricity':'Electrical','Hvac':'HVAC','Subcontracting Work On Modular Units - O':'Other modular works (review)'})
    t['Trade category']=t['Trade category'].replace('',U)
    return v,b,t

def csv(d): return d.to_csv(index=False).encode('utf-8-sig')
def money(v): return f'${v:,.0f}'
def agg(d,cols): return d.groupby(cols,dropna=False)['Amount'].sum().reset_index(name='Spend').sort_values('Spend',ascending=False)
def bar(d,c,title):
    st.plotly_chart(px.bar(d.head(20).sort_values('Spend'),x='Spend',y=c,orientation='h',title=title,template='plotly_white',color_discrete_sequence=['#167D83']),use_container_width=True)
@st.cache_data(ttl=900, show_spinner=False)
def fetch_private(repo, path, token):
    from urllib.parse import quote
    url = f'https://api.github.com/repos/{repo}/contents/{quote(path, safe="/")}'
    response = requests.get(url, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github.raw+json', 'X-GitHub-Api-Version': '2022-11-28'}, timeout=60)
    response.raise_for_status()
    return response.content
with st.sidebar:
    st.header('Project data')
    f=st.file_uploader('Replace workbook (optional)',type=['xlsx','csv'])
    st.caption('Default workbook loads automatically after login.')
try:
    local = Path(__file__).parent / 'data' / 'Subcontractor spend by branch.xlsx'
    if f: raw, name = f.getvalue(), f.name
    elif local.is_file(): raw, name = local.read_bytes(), local.name
    elif secret('DATA_REPO') and secret('DATA_TOKEN'):
        name = secret('DATA_PATH', 'Subcontractor spend by branch.xlsx')
        with st.spinner('Loading private workbook…'):
            raw = fetch_private(secret('DATA_REPO'), name, secret('DATA_TOKEN'))
    else:
        st.info('Configure the private default workbook in Streamlit Secrets, or upload a test workbook.'); st.stop()
    x=load(raw,name)
except Exception:
    st.error('Could not load workbook. Check private repository, token permissions, file path and workbook format.'); st.stop()
key=hashlib.sha256(raw).hexdigest()
if st.session_state.get('dataset')!=key:
    st.session_state.dataset=key; st.session_state.maps=mappings(x)
page=st.sidebar.radio('Workspace',['Overview','Spend cube','Supplier analysis','Trade concentration','Facility overlap','Spend trends','Rebate analysis','Transactions','Mappings & data quality'])
v,b,t=st.session_state.maps
if page=='Mappings & data quality':
    st.subheader('Editable mapping tables'); st.caption('ABN matches and branch state assignments are provisional. Confirm combined regions and factory definitions. Changes persist only in this session; export to reuse.')
    for i,(name,frame,keys) in enumerate(zip(['Vendor master','Branch / facility','Trade classification'],[v,b,t],[['Vendor No.'],['Branch Code','Branch'],['Trade']])):
        with st.expander(name,expanded=i==0):
            edited=st.data_editor(frame,column_config=numeric_config(frame),key=f'edit-{key}-{i}',disabled=keys,use_container_width=True,hide_index=True)
            st.download_button('Export mapping',csv(edited),f'mapping_{i}.csv',key=f'dl{i}')
            upload=st.file_uploader('Restore mapping CSV',type=['csv'],key=f'map{i}')
            if st.button('Apply changes',key=f'apply{i}'):
                new=pd.read_csv(upload,dtype=str,keep_default_na=False) if upload else edited
                if set(frame.columns)-set(new.columns) or new.duplicated(keys).any() or set(map(tuple,new[keys].astype(str).values))!=set(map(tuple,frame[keys].astype(str).values)) or any(new[c].astype(str).str.strip().eq('').any() for c in ({0:['Entity ID','Supplier'],1:['State','Facility','Facility type'],2:['Trade category']}[i])): st.error('Mapping must contain all original keys exactly once and all required columns and labels.')
                else:
                    maps=list(st.session_state.maps); maps[i]=new; st.session_state.maps=tuple(maps); st.rerun()
    st.subheader('Source quality checks'); st.write({'Rows':len(x),'Invalid dates':int(x['Posting Date'].isna().sum()),'Invalid amounts':int(x.Amount.isna().sum()),'Negative amounts':int(x.Amount.lt(0).sum()),'Missing ABN':int(x.ABN.eq('').sum()),'Repeated invoice numbers (additional lines, not necessarily duplicates)':int(x['Document No.'].duplicated().sum()),'Potential exact duplicate analytical lines (retained)':int(x.duplicated(['Posting Date','Vendor No.','Document No.','Order No.','Trade','Branch Code','Description','Description 2','Amount']).sum())}); st.warning('No explicit GL code is present. Department Code and Description are available as separate dimensions, not assumed GL codes.'); st.stop()
d=x.merge(v[['Vendor No.','Entity ID','Supplier','Vendor type']],on='Vendor No.',how='left',validate='many_to_one').merge(b,on=['Branch Code','Branch'],how='left',validate='many_to_one').merge(t,on='Trade',how='left',validate='many_to_one')
# Keep stable entity identifiers in aggregations, even if names match.
d['Supplier label']=d['Supplier']+' ['+d['Entity ID']+']'; d['Month']=d['Posting Date'].dt.to_period('M').astype(str); d['FY']='FY'+(d['Posting Date'].dt.year+(d['Posting Date'].dt.month>=7)).astype('Int64').astype(str)
with st.sidebar:
    st.header('Global filters'); group=st.radio('Supplier grouping',['Proposed entity (ABN)','Original vendor ID']);
    if group=='Original vendor ID': d['Supplier label']=d['Vendor Name']+' ['+d['Vendor No.']+']'
    national=d.copy()
    if page!='Rebate analysis':
        valid=d['Posting Date'].dropna()
        if len(valid):
            from datetime import date
            lo,hi=valid.min().date(),valid.max().date()
            default=(max(lo,date(2025,1,1)),min(hi,date(2026,1,1)))
            if default[0]>default[1]: default=(lo,hi+pd.Timedelta(days=1))
            dates=st.date_input('Posting date range (end exclusive)',default,min_value=lo,max_value=hi+pd.Timedelta(days=1),key='date-general-v3')
            if len(dates)==2: d=d[d['Posting Date'].ge(pd.Timestamp(dates[0]))&d['Posting Date'].lt(pd.Timestamp(dates[1]))]
    else: st.caption('Rebate analysis uses its own baseline date controls.')
    for c in ['State','Facility type','Facility','Trade category','Vendor type','Department Code','Supplier label']:
        opts=sorted(d[c].dropna().unique()); sel=st.multiselect(c,opts)
        if sel: d=d[d[c].isin(sel)]
    term=st.text_input('Search descriptions / supplier')
    if term: d=d[d[['Description','Description 2','Supplier label']].fillna('').apply(lambda s:s.str.contains(term,case=False,regex=False)).any(axis=1)]
st.caption('Net transaction amount excluding GST • Credits retained • Combined sales regions remain separate • ABN grouping is provisional')
if page=='Rebate analysis':
    from rebate import render_rebate
    render_rebate(d,national,key,display_table,csv)
    st.stop()
a=agg(d,['Supplier label']); total=d.Amount.sum(); positive=a[a.Spend>0]; den=positive.Spend.sum()
k=st.columns(4); k[0].metric('Net spend',money(total)); k[1].metric('Suppliers',f'{len(a):,}'); k[2].metric('Transaction lines',f'{len(d):,}'); k[3].metric('Top 5 share (positive supplier net spend)',f'{positive.head(5).Spend.sum()/den:.1%}' if den else 'N/A')
if d.empty: st.warning('No transactions match these filters.'); st.stop()
if page=='Overview':
    l,r=st.columns(2)
    with l: bar(agg(d,['Trade category']),'Trade category','Spend by trade')
    with r: bar(agg(d,['State']),'State','Spend by region')
    bar(a,'Supplier label','Top suppliers'); st.plotly_chart(px.line(agg(d,['Month']).sort_values('Month'),x='Month',y='Spend',markers=True),use_container_width=True)
elif page=='Spend cube':
    dims=['State','Facility','Facility type','Trade category','Supplier label','Vendor type','Department Code','Description','Month','FY']
    c1,c2=st.columns(2); rows=c1.multiselect('Group by',dims,default=['Trade category','Supplier label']); cols=c2.selectbox('Pivot columns',['None']+[c for c in dims if c not in rows]);
    if rows:
        out=agg(d,rows) if cols=='None' else pd.pivot_table(d,index=rows,columns=cols,values='Amount',aggfunc='sum',fill_value=0).reset_index()
        display_table(out,use_container_width=True,hide_index=True); st.download_button('Export cube',csv(out),'spend_cube.csv')
    else: st.info('Select a grouping dimension.')
elif page=='Supplier analysis':
    a['Net spend share']=a.Spend/total if total else 0; display_table(a,use_container_width=True,hide_index=True); st.download_button('Export supplier ranking',csv(a),'suppliers.csv'); sup=st.selectbox('Drill into supplier',a['Supplier label']); q=d[d['Supplier label']==sup]; l,r=st.columns(2)
    with l: bar(agg(q,['Facility']),'Facility','Facility spend')
    with r: bar(agg(q,['Description']),'Description','What is purchased')
    st.plotly_chart(px.line(agg(q,['Month']).sort_values('Month'),x='Month',y='Spend',markers=True),use_container_width=True); display_table(q[['Posting Date','Document No.','Trade category','Facility','Description','Description 2','Amount']],hide_index=True,use_container_width=True)
elif page=='Trade concentration':
    summary=[]
    for trade,q in d.groupby('Trade category'):
        z=agg(q,['Supplier label']); z=z[z.Spend>0]; base=z.Spend.sum(); share=z.Spend/base if base else z.Spend; summary.append({'Trade':trade,'Net spend':q.Amount.sum(),'Suppliers':q['Supplier label'].nunique(),'Top 1 share':share.head(1).sum(),'Top 5 share':share.head(5).sum(),'Suppliers to 80%':min(len(z),int((share.cumsum()<0.8).sum()+1)) if len(z) else 0,'HHI':(share**2).sum()*10000})
    st.caption('Concentration uses positive net supplier balances within each trade; negative-only suppliers are excluded from the concentration denominator.'); out=pd.DataFrame(summary); display_table(out,hide_index=True,use_container_width=True); st.download_button('Export concentration',csv(out),'concentration.csv'); tr=st.selectbox('Trade Pareto',sorted(d['Trade category'].unique())); z=agg(d[d['Trade category']==tr],['Supplier label']); z=z[z.Spend>0].copy(); z['Cumulative share']=z.Spend.cumsum()/z.Spend.sum(); z['Rank']=range(1,len(z)+1); st.plotly_chart(px.line(z,x='Rank',y='Cumulative share',hover_data=['Supplier label','Spend'],markers=True).update_yaxes(tickformat='.0%'),use_container_width=True)
elif page=='Facility overlap':
    dimension=st.radio('Compare across',['Facility','State'],horizontal=True); matrix=pd.pivot_table(d,index='Supplier label',columns=dimension,values='Amount',aggfunc='sum',fill_value=0); counts=d.groupby('Supplier label')[dimension].nunique(); matrix.insert(0,'Locations used',counts); matrix.insert(1,'Total net spend',a.set_index('Supplier label').Spend); matrix=matrix.sort_values('Total net spend',ascending=False); only=st.checkbox('Only suppliers used in multiple locations',value=True); matrix=matrix[matrix['Locations used']>1] if only else matrix; display_table(matrix,use_container_width=True); st.download_button('Export overlap',csv(matrix.reset_index()),'overlap.csv'); st.caption('Location count uses transaction presence, including locations whose net amount is zero.')
elif page=='Spend trends':
    period=st.radio('Period',['Month','FY'],horizontal=True); dim=st.selectbox('Breakdown',['Trade category','State','Facility','Supplier label']); z=agg(d,[period,dim]).sort_values(period); top=z.groupby(dim).Spend.sum().nlargest(12).index; st.plotly_chart(px.line(z[z[dim].isin(top)],x=period,y='Spend',color=dim,markers=True),use_container_width=True); st.caption('Top 12 series shown; all groups in export. Partial periods are not annualised.'); display_table(z,hide_index=True,use_container_width=True); st.download_button('Export trends',csv(z),'trends.csv')
else:
    fields=['Posting Date','Vendor No.','Supplier label','State','Facility','Trade category','Department Code','Document No.','Order No.','Description','Description 2','Quantity','UOM','Direct Unit Cost','Amount','Payment Terms','Blocked Vendor']; out=d[[c for c in fields if c in d]].sort_values('Posting Date',ascending=False); display_table(out,use_container_width=True,hide_index=True); st.download_button('Export transactions',csv(out),'transactions.csv')
