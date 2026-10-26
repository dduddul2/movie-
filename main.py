# 필요한 라이브러리 불러오기
import datetime
import requests
import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# 1. 기본 화면 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("어제의 박스오피스")
st.caption("영화진흥위원회 KOBIS 공식 API 기반 일일 영화 순위")


# --------------------------------------------------
# 2. 한국 시간 기준으로 어제 날짜 계산
# --------------------------------------------------

# 배포 서버가 해외 시간대를 사용해도 한국 날짜를 기준으로 계산한다.
KST = datetime.timezone(datetime.timedelta(hours=9))

# 현재 한국 날짜에서 하루를 뺀 날짜
yesterday = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)

# KOBIS API에서 요구하는 날짜 형식: YYYYMMDD
target_dt = yesterday.strftime("%Y%m%d")

st.info(f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} (한국 시간 기준)")


# --------------------------------------------------
# 3. KOBIS API 설정
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 4. API 데이터 가져오기
# --------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_boxoffice(date_str, api_key):
    """
    KOBIS API에 날짜와 인증키를 보내 영화 순위 데이터를 가져온다.
    정상적으로 데이터를 받으면 JSON 형식으로 반환한다.
    """

    params = {
        "key": api_key,
        "targetDt": date_str
    }

    # 최대 15초 동안 응답을 기다린다.
    response = requests.get(
        API_URL,
        params=params,
        timeout=15
    )

    # HTTP 오류가 발생하면 예외를 발생시킨다.
    response.raise_for_status()

    # JSON 데이터를 파이썬 딕셔너리로 변환한다.
    return response.json()


# --------------------------------------------------
# 5. 인증키 확인 및 API 요청
# --------------------------------------------------

try:
    # Streamlit Cloud의 Secrets에 저장한 인증키를 읽는다.
    # 인증키를 코드에 직접 작성하면 안 된다.
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        "KOBIS_KEY 항목이 등록되어 있는지 확인해 주세요."
    )
    st.code('KOBIS_KEY = "발급받은_인증키"')
    st.stop()

except Exception:
    st.error(
        "인증키 설정을 읽지 못했습니다. "
        "Streamlit Cloud의 Secrets 설정을 확인해 주세요."
    )
    st.stop()


# 인증키가 비어 있는 경우 확인한다.
if not str(api_key).strip():
    st.error(
        "KOBIS_KEY 값이 비어 있습니다. "
        "Secrets에 올바른 인증키를 입력해 주세요."
    )
    st.stop()


# API 요청을 실행한다.
try:
    data = fetch_boxoffice(target_dt, str(api_key).strip())

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버의 응답 시간이 초과되었습니다. "
        "잠시 기다린 뒤 페이지를 새로고침해 주세요."
    )
    st.stop()

except requests.exceptions.HTTPError as e:
    st.error(
        f"KOBIS 서버에서 HTTP 오류가 발생했습니다: {e}\n\n"
        "인터넷 연결과 API 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        f"KOBIS API에 연결하지 못했습니다: {e}\n\n"
        "네트워크 연결 또는 API 서버 상태를 확인해 주세요."
    )
    st.stop()

except ValueError:
    st.error(
        "API 응답을 JSON으로 읽지 못했습니다. "
        "KOBIS 서버가 정상적으로 응답하는지 확인해 주세요."
    )
    st.stop()

except Exception as e:
    st.error(f"데이터를 가져오는 중 예상하지 못한 오류가 발생했습니다: {e}")
    st.stop()


# --------------------------------------------------
# 6. API 오류 상자 확인
# --------------------------------------------------

# 인증키가 잘못된 경우 HTTP 상태코드는 200이어도
# 응답 안에 faultInfo가 들어올 수 있다.
if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다. 잠시 후 다시 시도해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo", {})

    # API가 보내 준 오류 메시지를 확인한다.
    error_message = fault.get("message", "상세 오류 메시지가 없습니다.")
    error_code = fault.get("errorCode", "오류 코드 없음")

    st.error("KOBIS API에서 오류 응답을 반환했습니다.")
    st.write(f"오류 코드: {error_code}")
    st.write(f"오류 내용: {error_message}")

    st.info(
        "확인할 사항\n"
        "1. Secrets의 KOBIS_KEY가 정확한지 확인하세요.\n"
        "2. KOBIS에서 발급받은 인증키인지 확인하세요.\n"
        "3. API 요청 주소와 요청 날짜 형식이 올바른지 확인하세요."
    )
    st.stop()


# --------------------------------------------------
# 7. 영화 목록 꺼내기
# --------------------------------------------------

boxoffice_result = data.get("boxOfficeResult")

if not isinstance(boxoffice_result, dict):
    st.error(
        "API 응답에 boxOfficeResult가 없습니다. "
        "KOBIS API 응답 구조와 서버 상태를 확인해 주세요."
    )
    st.stop()

movies = boxoffice_result.get("dailyBoxOfficeList", [])

if not isinstance(movies, list):
    st.error(
        "영화 목록의 형식이 올바르지 않습니다. "
        "API 응답 내용을 확인해 주세요."
    )
    st.stop()

if len(movies) == 0:
    st.warning(
        "해당 날짜의 영화 목록이 비어 있습니다."
    )
    st.info(
        "확인할 사항\n"
        "1. 어제 날짜의 박스오피스 집계가 완료되었는지 확인하세요.\n"
        "2. KOBIS 공식 박스오피스에서 같은 날짜를 조회해 보세요.\n"
        "3. 날짜와 API 응답 구조가 올바른지 확인하세요."
    )
    st.stop()


# --------------------------------------------------
# 8. 표와 그래프에 사용할 데이터 정리
# --------------------------------------------------

df = pd.DataFrame(movies)

# 화면에 필요한 열이 모두 있는지 확인한다.
required_columns = [
    "rank",
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
        "API 응답에서 필요한 항목을 찾을 수 없습니다: "
        + ", ".join(missing_columns)
    )
    st.info(
        "KOBIS API 응답 형식이 변경되었는지 확인해 주세요."
    )
    st.stop()


# 숫자 데이터가 문자열로 오므로 숫자 형식으로 변환한다.
number_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]

for col in number_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# 숫자로 변환되지 않은 행은 분석에서 제외한다.
df = df.dropna(subset=number_columns)

if df.empty:
    st.error(
        "영화 목록은 있지만 순위 또는 관객수 데이터가 올바르지 않습니다. "
        "KOBIS API 응답을 확인해 주세요."
    )
    st.stop()

# 순위가 빠른 영화가 위에 오도록 정렬한다.
df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------------
# 9. 1위 영화 지표 카드 3장
# --------------------------------------------------

top_movie = df.iloc[0]

st.divider()
st.subheader(f"일일 박스오피스 1위: {top_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{int(top_movie['audiCnt']):,}명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{int(top_movie['audiAcc']):,}명"
    )

with col3:
    st.metric(
        label="스크린 수",
        value=f"{int(top_movie['scrnCnt']):,}개"
    )


# --------------------------------------------------
# 10. 전체 영화 순위표
# --------------------------------------------------

st.divider()
st.subheader("전체 영화 순위")

# 표에 표시할 열을 선택하고 한국어로 이름을 바꾼다.
table_df = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 날짜가 없는 경우에는 미표시 기호로 나타낸다.
table_df["개봉일"] = table_df["개봉일"].replace("", "정보 없음").fillna("정보 없음")

# 큰 숫자를 읽기 쉽게 천 단위 쉼표로 표시한다.
for col in ["순위", "관객수", "누적관객", "스크린수"]:
    table_df[col] = table_df[col].map(lambda x: f"{int(x):,}")

st.dataframe(
    table_df,
    hide_index=True,
    use_container_width=True
)


# --------------------------------------------------
# 11. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.divider()
st.subheader("관객수 상위 5편")

# 어제 관객수가 많은 영화부터 5편을 선택한다.
top5 = df.sort_values(
    "audiCnt",
    ascending=False
).head(5).copy()

# 그래프에서 영화명을 가나다순이 아니라 관객수 순서로 표시한다.
top5["관객수"] = top5["audiCnt"].astype(int)

fig = px.bar(
    top5.sort_values("관객수", ascending=True),
    x="관객수",
    y="movieNm",
    orientation="h",
    text="관객수",
    labels={
        "movieNm": "영화명",
        "관객수": "어제 관객수(명)"
    },
    title="어제 관객수 TOP 5"
)

# 막대 끝에 관객수를 표시한다.
fig.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside",
    cliponaxis=False
)

fig.update_layout(
    yaxis_title="영화명",
    xaxis_title="관객수(명)",
    showlegend=False,
    height=400,
    margin=dict(l=20, r=80, t=60, b=30)
)

st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------
# 12. 데이터 출처
# --------------------------------------------------

st.divider()

st.caption(
    "데이터 출처: 영화진흥위원회 영화관입장권통합전산망(KOBIS) "
    "| 집계 결과는 사후 정정될 수 있습니다."
)

st.link_button(
    "KOBIS 공식 박스오피스 확인",
    "https://www.kobis.or.kr/kobis/business/stat/boxs/findDailyBoxOfficeList.do"
)
