import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="haksalturn520v0.1", layout="wide")
st.title("🚀 haksalturn520v0.1")

# --- 사이드바: 필터 설정 ---
st.sidebar.header("🔍 검색 필터 설정")

# 1. 시장 선택
markets = []
col1, col2 = st.sidebar.columns(2)
if col1.checkbox("KOSPI", value=True): markets.append("KOSPI")
if col2.checkbox("KOSDAQ", value=True): markets.append("KOSDAQ")

# 2. 규모 선택
sizes = []
s_col1, s_col2, s_col3 = st.sidebar.columns(3)
if s_col1.checkbox("대형주"): sizes.append("대형주")
if s_col2.checkbox("중형주"): sizes.append("중형주")
if s_col3.checkbox("소형주"): sizes.append("소형주")

# 3. 업종 선택
all_sectors = ["전체", "반도체", "제약", "소프트웨어", "자동차", "금융", "화학", "건설", "엔터테인먼트"]
selected_sectors = st.sidebar.multiselect("대상 업종 선택 (미선택 시 전체)", all_sectors, default=["전체"])

# --- 메인 화면 제어 버튼 ---
m_col1, m_col2 = st.columns([1, 5])
start_button = m_col1.button("🔍 스캔 시작", use_container_width=True)
stop_placeholder = m_col2.empty()

# 결과 저장용 리스트
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = []

if start_button:
    st.session_state.scan_results = [] # 초기화
    
    # 1. 전종목 리스트 확보
    with st.spinner("KRX 전종목 리스트를 불러오는 중..."):
        df_krx = fdr.StockListing('KRX')
        
        # 컬럼명 보정 (FDR 버전 대응)
        if 'Symbol' not in df_krx.columns and 'Code' in df_krx.columns:
            df_krx = df_krx.rename(columns={'Code': 'Symbol'})
        
        # 시장 필터 적용
        target_df = df_krx[df_krx['Market'].isin(markets)].copy()
        
        # 업종 필터 적용
        if selected_sectors and "전체" not in selected_sectors:
            target_df = target_df[target_df['Sector'].str.contains('|'.join(selected_sectors), na=False)]
        
        # 규모 필터 적용 (시총 순위 기준)
        if 'Marcap' in target_df.columns:
            target_df = target_df.sort_values(by='Marcap', ascending=False)
            if sizes:
                temp = []
                if '대형주' in sizes: temp.append(target_df.iloc[:100])
                if '중형주' in sizes: temp.append(target_df.iloc[100:300])
                if '소형주' in sizes: temp.append(target_df.iloc[300:])
                if temp: target_df = pd.concat(temp)

    # 2. 상세 스캔 루프
    target_list = target_df.to_dict('records')
    total = len(target_list)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    table_placeholder = st.empty()
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")

    for idx, row in enumerate(target_list):
        symbol = row.get('Symbol')
        name = row.get('Name')
        
        # 상태 업데이트
        percent = int((idx + 1) / total * 100)
        progress_bar.progress(percent)
        status_text.text(f"[{idx+1}/{total}] {name} 분석 중...")

        try:
            df = fdr.DataReader(symbol, start_date, end_date)
            if len(df) < 40: continue

            # [조건 1] 40일 이내 상한가 이력
            df_40 = df.iloc[-40:]
            if not any(df_40['Close'].pct_change() >= 0.29): continue

            # [조건 2] 이평선 계산
            close = df['Close']
            ma5 = close.rolling(5).mean().iloc[-1]
            ma10 = close.rolling(10).mean().iloc[-1]
            ma15 = close.rolling(15).mean().iloc[-1]
            ma20 = close.rolling(20).mean().iloc[-1]
            ma20_prev = close.rolling(20).mean().iloc[-2]
            curr = close.iloc[-1]

            # [조건 3] 기술적 타점 (밀집/횡보/위치)
            ma_list = [ma5, ma10, ma15, ma20]
            is_compact = (max(ma_list) - min(ma_list)) / curr <= 0.03 # 3% 밀집
            is_flat = ma20 <= ma20_prev * 1.002 # 하락 혹은 횡보
            is_pos = curr >= ma5 and curr >= ma20 # 5, 20일선 위
            is_dist = (curr - ma20) / ma20 <= 0.10 # 10% 이격

            if is_compact and is_flat and is_pos and is_dist:
                m_open = df['Open'].iloc[-20] if len(df) >= 20 else df['Open'].iloc[0]
                m_high = df['High'].iloc[-20:].max()
                
                res = {
                    "업종": str(row.get('Sector', row.get('Market'))),
                    "종목명": name,
                    "시가총액": f"{row.get('Marcap', 0)/100000000:,.0f}억",
                    "현재가": f"{curr:,.0f}",
                    "상승률": f"{(curr - close.iloc[-2])/close.iloc[-2]*100:+.2f}%",
                    "한달전시가비": f"{(curr - m_open)/m_open*100:+.2f}%",
                    "한달전고점비": f"{(curr - m_high)/m_high*100:+.2f}%"
                }
                st.session_state.scan_results.append(res)
                
                # 실시간 테이블 업데이트
                table_placeholder.table(pd.DataFrame(st.session_state.scan_results))
        except:
            continue

    status_text.success(f"✅ 스캔 완료! 총 {len(st.session_state.scan_results)}개 종목 포착")

# --- 결과 출력 및 엑셀 다운로드 ---
if st.session_state.scan_results:
    final_df = pd.DataFrame(st.session_state.scan_results)
    
    st.divider()
    st.subheader("📊 최종 포착 결과")
    st.dataframe(final_df, use_container_width=True)
    
    # 엑셀 다운로드 버튼
    csv = final_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 결과 엑셀(CSV) 다운로드",
        data=csv,
        file_name=f"haksalturn520v0.1_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime='text/csv',
    )
