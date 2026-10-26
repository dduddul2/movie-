
import datetime
from zoneinfo import ZoneInfo

import requests
import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# 1. 기본 화면 설정
# --------------------------------------------------

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("박스오피스 조회")
st.caption("영화진흥위원회 KOBIS 공식 일별 박스오피스")


# --------------------------------------------------
# 2. 한국 시간과 날짜 설정
# --------------------------------------------------

# 서버가 어느 나라에 있든 한국 시간으로 날짜를 계산한다.
KST = ZoneInfo("Asia/Seoul")
today = datetime.datetime.now(KST).date()
yesterday = today - datetime.timedelta(days=1)

# 조회할 수 있는 날짜 범위
earliest_date = datetime.date(1900, 1, 1)


# --------------------------------------------------
# 3. 날짜 선택 달력
# --------------------------------------------------

st.subheader("조회 날짜 선택")

selected_date = st.date_input(
    "박스오피스를 확인할 날짜",
    value=yesterday,
    min_value=earliest_date,
    max_value=yesterday,
    format="YYYY-MM-DD"
)

# KOBIS API에서 사용하는 날짜 형식으로 변환한다.
target_dt = selected_date.strftime("%Y%m%d")

st.info(
    f"선택한 날짜: {selected_date.strftime('%Y년 %m월 %d일')}"
)


# --------------------------------------------------
# 4. KOBIS API 주소
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 5. API 데이터 요청 함수
# --------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_boxoffice(date_str, api_key):
    # 선택한 날짜와 인증키를 API에 전달한다.
    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_str
        },
        timeout=15
    )

    # HTTP 오류가 있으면 예외를 발생시킨다.
    response.raise_for_status()

    # JSON 응답을 파이썬 자료형으로 변환한다.
    return response.json()


# --------------------------------------------------
# 6. 인증키 확인
# --------------------------------------------------

try:
    # 인증키는 Streamlit Cloud의 Secrets에서 읽는다.
    # 실제 인증키를 코드에 직접 입력하지 않는다.
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "KOBIS_KEY 인증키가 없습니다. "
        "Streamlit Cloud의 앱 설정 → Secrets에서 "
        "인증키를 등록해 주세요."
    )
    st.stop()

except Exception:
    st.error(
        "Secrets 설정을 읽을 수 없습니다. "
        "Streamlit Cloud의 인증키 설정을 확인해 주세요."
    )
    st.stop()

if not str(api_key).strip():
    st.error(
        "KOBIS_KEY 값이 비어 있습니다. "
        "Secrets에 발급받은 인증키를 입력해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 7. API 요청과 예외 처리
# --------------------------------------------------

try:
    data = fetch_boxoffice(
        target_dt,
        str(api_key).strip()
    )

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버 응답 시간이 초과되었습니다. "
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()

except requests.exceptions.HTTPError:
    st.error(
        "KOBIS 서버에서 HTTP 오류가 발생했습니다. "
        "서버 상태와 인터넷 연결을 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException:
    st.error(
        "KOBIS API에 연결할 수 없습니다. "
        "인터넷 연결과 API 서버 상태를 확인해 주세요."
    )
    st.stop()

except ValueError:
    st.error(
        "API 응답을 JSON으로 읽지 못했습니다. "
        "KOBIS 서버 응답을 확인해 주세요."
    )
    st.stop()

except Exception:
    st.error(
        "데이터 요청 중 예상하지 못한 오류가 발생했습니다. "
        "설정과 API 응답을 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 8. API 응답과 인증키 오류 확인
# --------------------------------------------------

if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다.")
    st.stop()

# 인증키가 틀리면 상태코드가 200이어도 오류 상자가 올 수 있다.
if "faultInfo" in data:
    fault = data.get("faultInfo", {})

    if not isinstance(fault, dict):
        fault = {}

    st.error("KOBIS API에서 오류 응답을 반환했습니다.")
    st.write(
        "오류 코드:",
        fault.get("errorCode", "확인할 수 없음")
    )
    st.write(
        "오류 내용:",
        fault.get("message", "상세 메시지가 없습니다.")
    )

    st.info(
        "Secrets의 KOBIS_KEY가 올바른지, "
        "API 요청 주소와 날짜 형식이 맞는지 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 9. 영화 목록 확인
# --------------------------------------------------

boxoffice_result = data.get("boxOfficeResult")

if not isinstance(boxoffice_result, dict):
    st.error(
        "API 응답에 박스오피스 결과가 없습니다. "
        "KOBIS 서버 상태와 응답 구조를 확인해 주세요."
    )
    st.stop()

movies = boxoffice_result.get("dailyBoxOfficeList", [])

if not isinstance(movies, list):
    st.error(
        "영화 목록의 형식이 올바르지 않습니다. "
        "API 응답을 확인해 주세요."
    )
    st.stop()

# 선택한 날짜에 영화 목록이 없을 때 표시한다.
if len(movies) == 0:
    st.warning("그날은 아직 집계 전입니다")
    st.info(
        "선택한 날짜의 집계 자료가 아직 제공되지 않을 수 있습니다. "
        "날짜가 올바른지 확인하거나 다른 날짜를 선택해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 10. 데이터 정리
# --------------------------------------------------

df = pd.DataFrame(movies)

# 순위 변화 항목도 함께 확인한다.
required_columns = [
    "rank",
    "rankInten",
    "movieNm",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    st.error(
        "응답에 필요한 항목이 없습니다: "
        + ", ".join(missing_columns)
    )
    st.info("KOBIS API의 응답 구조를 확인해 주세요.")
    st.stop()

# API 숫자 값은 문자열이므로 숫자로 변환한다.
number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

for col in number_columns:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

# 필수 숫자 항목을 읽지 못한 행은 제외한다.
df = df.dropna(subset=number_columns)

if df.empty:
    st.error(
        "영화 데이터의 숫자 항목을 읽을 수 없습니다. "
        "KOBIS API 응답을 확인해 주세요."
    )
    st.stop()

# 순위 순서대로 정렬한다.
df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------------
# 11. 영화명, 순위 변화, 트로피 표시
# --------------------------------------------------

def format_rank_change(value):
    """
    순위 변화 값을 화살표와 함께 표시한다.
    요청한 규칙에 따라 양수는 상승, 음수는 하락이다.
    """
    value = int(value)

    if value > 0:
        return f"▲ {value}"
    elif value < 0:
        return f"▼ {abs(value)}"
    else:
        return "—"


# 누적 관객수가 100만 명을 초과하면 트로피를 붙인다.
def format_movie_name(name, audience_total):
    if int(audience_total) > 1_000_000:
        return f"🏆 {name}"
    return name


# 표에 표시할 데이터만 따로 복사한다.
table_df = df[
    [
        "rank",
        "rankInten",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

table_df["순위 변화"] = table_df["rankInten"].apply(
    format_rank_change
)

table_df["영화명"] = [
    format_movie_name(name, total)
    for name, total in zip(
        table_df["movieNm"],
        table_df["audiAcc"]
    )
]

# 표의 열 이름을 한국어로 변경한다.
table_df = table_df[
    [
        "rank",
        "순위 변화",
        "영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
]

table_df.columns = [
    "순위",
    "순위 변화",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 개봉일 정보가 없으면 안내 문구를 표시한다.
table_df["개봉일"] = (
    table_df["개봉일"]
    .replace("", "정보 없음")
    .fillna("정보 없음")
)


# --------------------------------------------------
# 12. 1위 영화 지표 카드
# --------------------------------------------------

top_movie = df.iloc[0]

st.divider()
st.subheader(f"박스오피스 1위: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{int(top_movie['audiCnt']):,}명"
    )

with col2:
    st.metric(
        "누적관객",
        f"{int(top_movie['audiAcc']):,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{int(top_movie['scrnCnt']):,}개"
    )


# --------------------------------------------------
# 13. 전체 박스오피스 표
# --------------------------------------------------

st.divider()
st.subheader("전체 영화 순위")

# 화살표 색상을 CSS로 지정한다.
def color_rank_change(value):
    if str(value).startswith("▲"):
        return "color: red; font-weight: bold"
    elif str(value).startswith("▼"):
        return "color: blue; font-weight: bold"
    return "color: gray"


# 숫자는 천 단위 쉼표로 표시한다.
styled_table = (
    table_df.style
    .format(
        {
            "순위": "{:,.0f}",
            "관객수": "{:,.0f}",
            "누적관객": "{:,.0f}",
            "스크린수": "{:,.0f}"
        },
        na_rep="정보 없음"
    )
    .map(
        color_rank_change,
        subset=["순위 변화"]
    )
)

st.dataframe(
    styled_table,
    hide_index=True,
    use_container_width=True
)

st.caption(
    "▲ 빨간색: 순위 상승  |  "
    "▼ 파란색: 순위 하락  |  "
    "—: 순위 변화 없음 또는 신규 진입 등 변화량 0"
)


# --------------------------------------------------
# 14. 관객수 상위 5편 그래프
# --------------------------------------------------

st.divider()
st.subheader("관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)

# 그래프의 막대 끝에 표시할 관객수
top5["관객수"] = top5["audiCnt"].astype(int)

# 수평 막대그래프를 생성한다.
fig = px.bar(
    top5.sort_values("관객수", ascending=True),
    x="관객수",
    y="movieNm",
    orientation="h",
    text="관객수",
    labels={
        "movieNm": "영화명",
        "관객수": "관객수(명)"
    },
    title="선택한 날짜의 관객수 TOP 5"
)

fig.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside",
    cliponaxis=False
)

fig.update_layout(
    xaxis_title="관객수(명)",
    yaxis_title="영화명",
    showlegend=False,
    height=400,
    margin=dict(l=20, r=80, t=60, b=30)
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# --------------------------------------------------
# 15. 데이터 출처
# --------------------------------------------------

st.divider()

st.caption(
    "데이터 출처: 영화진흥위원회 영화관입장권통합전산망(KOBIS). "
    "집계 자료는 추후 수정될 수 있습니다."
)

st.link_button(
    "KOBIS 공식 박스오피스 확인",
    "https://www.kobis.or.kr/kobis/business/stat/boxs/findDailyBoxOfficeList.do"
)
