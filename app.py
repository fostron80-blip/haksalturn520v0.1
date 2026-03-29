import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 페이지 설정 ---
st.set_page_config(page_title="haksalturn520v0.1", layout="wide")
st.title("🚀 haksalturn520v0.1 (Visual Chart Scanner)")

# --- 데이터 캐싱 ---
@st.cache_data(ttl=3600)
def get_krx_list():
    df = fdr.StockListing('KRX')
    if 'Symbol' not in df.columns and 'Code' in df.columns:
        df = df.rename(columns={'Code': 'Symbol'})
    return df

# --- 사이드바 설정 ---
st.sidebar.header("🔍 검색 필터")
markets = st.sidebar.multiselect("시장 선택", ["KOSPI", "KOSDAQ"], default=["KOSPI", "KOSDAQ"])
sizes = st.sidebar.multiselect("규모 선택", ["대형주", "중형주", "소형주"], default=["소형주"])

df_base = get_krx_list()
raw_sectors = sorted(df_base['Sector'].dropna().unique().tolist())
selected_sectors = st.sidebar.multiselect("대상 업종 선택", ["전체"] + raw_sectors, default=["전체"])

# --- 메인 실행 ---
if st.button("🔍 조건검색 및 차트 생성 시작", use_container_width=True):
    st.session_state.scan_results = []
    
    # 필터링 로직
    target_df = df_base[df_base['Market'].isin(markets)].copy()
    if selected_sectors and "전체" not in selected_sectors:
        target_df = target_df[target_df['Sector'].isin(selected_sectors)]
    
    if sizes and 'Marcap' in target_df.columns:
        target_df = target_df.sort_values(by='Marcap', ascending=False)
        temp = []
        if '대형주' in sizes: temp.append(target_df.iloc[:100])
        if '중형주' in sizes: temp.append(target_df.iloc[100:300])
        if '소형주' in sizes: temp.append(target_df.iloc[300:])
        if temp: target_df = pd.concat(temp)

    target_list = target_df.to_dict('records')
    total = len(target_list)
    pb = st.progress(0)
    status = st.empty()
    
    # 데이터 수집 기간
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")

    for idx, row in enumerate(target_list):
        symbol, name = row.get('Symbol'), row.get('Name')
        pb.progress(int((idx + 1) / total * 100))
        status.text(f"[{idx+1}/{total}] {name} 분석 및 차트 생성 중...")

        try:
            df = fdr.DataReader(symbol, start_date, end_date)
            if len(df) < 60: continue

            close = df['Close']
            high = df['High']
            low = df['Low']

            # [조건 A] 40봉 이내 상한가
            if not any(df.iloc[-40:]['Close'].pct_change() >= 0.29): continue

            # [조건 B, F, C] 이평선 밀집 및 정배열
            ma5 = close.rolling(5).mean()
            ma10 = close.rolling(10).mean()
            ma20 = close.rolling(20).mean()
            
            curr_ma = [ma5.iloc[-1], ma10.iloc[-1], ma20.iloc[-1]]
            is_converged = (max(curr_ma) - min(curr_ma)) / close.iloc[-1] <= 0.05
            is_aligned = ma5.iloc[-1] >= ma10.iloc[-1] >= ma20.iloc[-1]

            # [조건 G, I] 일목균형표
            tenkan_sen = (high.rolling(9).max() + low.rolling(9).min()) / 2
            kijun_sen = (high.rolling(26).max() + low.rolling(26).min()) / 2
            is_ichimoku_ok = close.iloc[-1] >= tenkan_sen.iloc[-1] and close.iloc[-1] >= kijun_sen.iloc[-1]

            # 모든 조건 충족 시 차트 출력
            if is_converged and is_aligned and is_ichimoku_ok:
                st.subheader(f"📈 포착 종목: {name} ({symbol})")
                
                # Plotly 차트 생성
                fig = go.Figure(data=[go.Candlestick(
                    x=df.index[-100:],
                    open=df['Open'][-100:], high=df['High'][-100:],
                    low=df['Low'][-100:], close=df['Close'][-100:],
                    name='Candle'
                )])
                
                # 지표 추가
                fig.add_trace(go.Scatter(x=df.index[-100:], y=ma20[-100:], name='20일선', line=dict(color='orange', width=1.5)))
                fig.add_trace(go.Scatter(x=df.index[-100:], y=tenkan_sen[-100:], name='일목-전환선', line=dict(color='blue', dash='dot')))
                fig.add_trace(go.Scatter(x=df.index[-100:], y=kijun_sen[-100:], name='일목-기준선', line=dict(color='red', dash='dot')))
                
                fig.update_layout(height=500, xaxis_rangeslider_visible=False, template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)
                
                st.session_state.scan_results.append({
                    "업종": row.get('Sector'), "종목명": name, "현재가": f"{close.iloc[-1]:,.0f}",
                    "상승률": f"{(close.iloc[-1]-close.iloc[-2])/close.iloc[-2]*100:+.2f}%"
                })
        except:
            continue
    status.success(f"✅ 완료! {len(st.session_state.scan_results)}개 종목의 차트를 불러왔습니다.")

# 결과 요약 테이블
if st.session_state.get('scan_results'):
    with st.expander("📋 포착 종목 리스트 요약 보기"):
        st.table(pd.DataFrame(st.session_state.scan_results))
