import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 디자인 (따뜻한 톤 스타일링)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="👨‍👩‍👧‍👦",
    layout="wide",
)

# 따뜻한 톤 스타일 커스텀 CSS 적용
st.markdown(
    """
    <style>
    /* 전체 배경색 및 기본 글꼴 설정 */
    .main {
        background-color: #FAF7F2;
    }
    /* 카드/컨테이너 배경 */
    div[data-testid="stBlock"] {
        background-color: #FFFDF9;
        border-radius: 10px;
        padding: 15px;
    }
    /* 타이틀 색상 */
    h1 {
        color: #5A4035;
        font-weight: 700;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리 (캐시 적용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    """지정된 GitHub URL에서 ZIP 압축 CSV 데이터를 읽어오고 최신 연도 데이터를 추출합니다."""
    url = "https://raw.githubusercontent.com/first2022-cyber/contents/main/population_ts_yearly_gender.zip"

    # 판다스로 ZIP 내 CSV 데이터 직접 읽기 (EUC-KR 또는 UTF-8 인코딩 처리)
    try:
        df = pd.read_csv(url, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(url, encoding="euc-kr")

    # '연도' 열에서 가장 최신 연도 찾기 및 최신 연도 데이터 필터링
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    return df_latest, latest_year


# 데이터 로딩 실행
try:
    df, latest_year = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 메인 화면 헤더
# -----------------------------------------------------------------------------
st.title("👨‍👩‍👧‍👦 동네별 인구 피라미드")
st.write(
    f"우리 동네의 나이별·성별 인구 구조를 한눈에 확인해보세요. (기준 연도: **{latest_year}년**)"
)
st.markdown("---")

# -----------------------------------------------------------------------------
# 4. 드롭다운 선택 상자 (시도 -> 시군구 -> 동)
# -----------------------------------------------------------------------------
st.subheader("📍 지역 선택")
col1, col2, col3 = st.columns(3)

# 1) 시도 선택
sido_list = sorted(df["시도"].dropna().unique())
with col1:
    selected_sido = st.selectbox("시·도 선택", sido_list)

# 선택한 시도에 해당하는 데이터 필터링
df_sido = df[df["시도"] == selected_sido]

# 2) 시군구 선택
sigungu_list = sorted(df_sido["시군구"].dropna().unique())
with col2:
    selected_sigungu = st.selectbox("시·군·구 선택", sigungu_list)

# 선택한 시군구에 해당하는 데이터 필터링
df_sigungu = df_sido[df_sido["시군구"] == selected_sigungu]

# 3) 동 선택
dong_list = sorted(df_sigungu["동"].dropna().unique())
with col3:
    selected_dong = st.selectbox("읍·면·동 선택", dong_list)

# 최종 선택된 지역의 1개 행 추출
selected_row = df_sigungu[df_sigungu["동"] == selected_dong].iloc[0]

# -----------------------------------------------------------------------------
# 5. 인구 데이터 정리 및 라벨 순서 고정
# -----------------------------------------------------------------------------
# 나이 라벨 생성 (0세, 1세, ..., 99세, 100세 이상)
age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]

male_pop = []  # 남자 인구수 (음수로 저장)
female_pop = []  # 여자 인구수 (양수로 저장)

for age in age_labels:
    # 컬럼 이름 형식: '남_0세', '여_0세', '남_100세 이상'
    m_col = f"남_{age}"
    f_col = f"여_{age}"

    # 데이터 추출 (값이 없으면 0으로 처리)
    m_val = selected_row.get(m_col, 0)
    f_val = selected_row.get(f_col, 0)

    # Plotly 시각화를 위해 남자는 음수(-), 여자는 양수(+)로 변경
    male_pop.append(-int(m_val))
    female_pop.append(int(f_val))

# -----------------------------------------------------------------------------
# 6. Plotly 인구 피라미드 가로 막대그래프 생성
# -----------------------------------------------------------------------------
fig = go.Figure()

# 남자 데이터 (왼쪽, 음수값) - 따뜻한 블루계열/인디고
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=male_pop,
        name="남자",
        orientation="h",
        marker=dict(color="#6B8E23"),  # 따뜻한 느낌의 올리브 그린
        hovertemplate="남자 %{y}: %{customdata}명<extra></extra>",
        customdata=[abs(x) for x in male_pop],  # 툴팁에는 양수로 표시
    )
)

# 여자 데이터 (오른쪽, 양수값) - 따뜻한 핑크/테라코타계열
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=female_pop,
        name="여자",
        orientation="h",
        marker=dict(color="#E07A5F"),  # 따뜻한 느낌의 테라코타 붉은색
        hovertemplate="여자 %{y}: %{x}명<extra></extra>",
    )
)

# 축 레이아웃 지정 및 나이 축(0세~100세 이상) 순서 고정
fig.update_layout(
    title=dict(
        text=f"<b>{selected_sido} {selected_sigungu} {selected_dong}</b> 인구 피라미드",
        font=dict(size=20, color="#5A4035"),
        x=0.5,
        xanchor="center",
    ),
    barmode="overlay",  # 두 막대를 중심에 맞춤
    bargap=0.1,  # 막대 간격
    paper_bgcolor="#FFFDF9",
    plot_bgcolor="#FFFDF9",
    height=800,  # 100개 이상의 나이 축이 잘 보이도록 높이 지정
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
    ),
    xaxis=dict(
        title="인구수 (명)",
        # x축 눈금 레이아웃을 절대값(양수)으로 표시
        tickmode="array",
        tickvals=[
            -10000,
            -5000,
            -2000,
            -1000,
            -500,
            0,
            500,
            1000,
            2000,
            5000,
            10000,
        ],
        ticktext=[
            "10,000",
            "5,000",
            "2,000",
            "1,000",
            "500",
            "0",
            "500",
            "1,000",
            "2,000",
            "5,000",
            "10,000",
        ],
        gridcolor="#EFEAE1",
    ),
    yaxis=dict(
        title="나이",
        # 중요: 0세부터 100세 이상까지 순서를 고정하여 0세가 맨 아래에 오도록 설정
        type="category",
        categoryorder="array",
        categoryarray=age_labels,
        gridcolor="#EFEAE1",
        dtick=5,  # 5세 단위로 눈금 라벨 표출
    ),
)

# -----------------------------------------------------------------------------
# 7. 화면 출력
# -----------------------------------------------------------------------------
st.plotly_chart(fig, use_container_width=True)

# 주요 요약 정보 표시
total_m = sum(abs(x) for x in male_pop)
total_f = sum(female_pop)
total_pop = total_m + total_f

col_a, col_b, col_c = st.columns(3)
col_a.metric("전체 인구수", f"{total_pop:,} 명")
col_b.metric("남성 인구수", f"{total_m:,} 명")
col_c.metric("여성 인구수", f"{total_f:,} 명")
