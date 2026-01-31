import streamlit as st
import google.generativeai as genai
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pandas as pd
import html

st.set_page_config(
    page_title="시디즈 UX 라이팅 가이드",
    page_icon="✏️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.response-container {
    position: relative;
    padding: 10px 0;
}

.copy-button {
    position: absolute;
    right: 0;
    bottom: 0;
    background: transparent;
    border: none;
    cursor: pointer;
    transition: opacity 0.2s;
    font-size: 18px;
    padding: 5px 10px;
}

.copy-button:hover {
    opacity: 1 !important;
}

.source-link {
    color: #0066cc;
    text-decoration: none;
}

.source-link:hover {
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

def get_gsheet_client():
    try:
        if "gcp_service_account" not in st.secrets:
            return None
            
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.sidebar.warning("⚠️ Google Sheets 연동 안됨")
        return None

def save_feedback_to_sheet(original_text, converted_text, feedback, mode, reason="", comment=""):
    try:
        client = get_gsheet_client()
        if client is None:
            return False
        
        sheet_url = st.secrets.get("feedback_sheet_url", "")
        if not sheet_url:
            return False
        
        sheet = client.open_by_url(sheet_url).sheet1
        
        if sheet.row_count == 0 or sheet.cell(1, 1).value != "시간":
            sheet.insert_row(["시간", "모드", "원본 문구", "변환된 문구", "피드백", "피드백값", "싫어요 사유", "코멘트"], 1)
        
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            mode,
            original_text,
            converted_text,
            "👍" if feedback == 1 else "👎",
            feedback,
            reason,
            comment
        ]
        
        sheet.append_row(row)
        return True
        
    except Exception as e:
        return False

def load_negative_feedback():
    try:
        client = get_gsheet_client()
        if client is None:
            return ""
        
        sheet_url = st.secrets.get("feedback_sheet_url", "")
        if not sheet_url:
            return ""
        
        sheet = client.open_by_url(sheet_url).sheet1
        records = sheet.get_all_records()
        
        if not records:
            return ""
        
        df = pd.DataFrame(records)
        negative_df = df[df['피드백값'] == 0]
        
        if negative_df.empty:
            return ""
        
        negative_examples = ""
        for _, row in negative_df.tail(10).iterrows():
            negative_examples += f"""
원본: "{row['원본 문구']}"
나쁜 변환: "{row['변환된 문구']}" 
사유: {row.get('싫어요 사유', 'N/A')}
코멘트: {row.get('코멘트', 'N/A')}
← 이런 스타일 절대 피하기
"""
        
        return f"""
[사용자가 싫어한 변환 스타일 - 절대 사용 금지]
{negative_examples}
"""
        
    except Exception as e:
        return ""

try:
    GOOGLE_API_KEY = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
except KeyError as e:
    st.error(f"❌ Secrets 설정 오류: {e}")
    st.stop()

@st.cache_resource
def get_gemini_model():
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    return genai.GenerativeModel(target)

def get_gemini_model_with_search():
    """웹 검색 기능이 활성화된 모델 - SEARCH 모드 전용"""
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
    # 웹 검색은 Gemini API에서 기본 제공되지 않을 수 있음
    # 일반 모델로 폴백하되, 프롬프트에서 "검색하라"고 명시
    return genai.GenerativeModel(target)

def generate_prompt(mode, user_input, negative_feedback):
    base_instruction = f"""
너는 시디즈의 전문 UX 라이터야. 사용자가 입력한 일반 문구를 시디즈만의 브랜드 보이스로 변환해줘.

[시디즈 브랜드 보이스 핵심]
- 전문적이면서도 따뜻한 조력자
- 사용자 중심의 세심한 배려
- 혁신과 지속가능성에 대한 진정성

{negative_feedback}
"""
    
    if mode == "UX":
        mode_instruction = """
[UX 모드 - 브랜드 감성 & 친절한 조력자]

변환 시 다음에 집중하세요:
1. 감성적 연결: 사용자의 감정과 니즈에 공감하는 표현
2. 친절한 안내: 전문적이되 따뜻하고 접근하기 쉬운 톤
3. 경험 중심: 제품의 스펙보다 사용자가 느낄 경험을 강조
4. 신뢰감: 과장 없이 진솔하고 믿을 수 있는 표현

변환 예시:
원본: "편안한 의자"
변환: "하루 종일 앉아 있어도 지치지 않도록, 당신의 몸을 세심하게 배려한 시팅 경험을 제공합니다"

중요: 출처 URL은 포함하지 마세요.
"""
    
    elif mode == "SEARCH":
        mode_instruction = """
[홈페이지 정보 탐색 모드]

**중요: 답변하기 전에 반드시 시디즈 공식 홈페이지(kr.sidiz.com)를 검색하여 최신 정보를 확인하세요.**

사용자의 질문에 답하기 위해 다음을 수행하세요:
1. 먼저 "site:kr.sidiz.com [질문 내용]"으로 웹 검색
2. 검색 결과에서 관련 정보 확인
3. 정확한 정보를 바탕으로 답변 작성

검색 범위:
- 제품 스펙 및 상세 정보
- 품질보증 기간 및 A/S 정책
- 배송 정보 및 예상 일정
- FAQ 및 고객센터 안내
- 매장 위치 및 영업 시간

답변 형식:
1. 검색으로 확인된 정확한 정보
2. 추가로 도움이 될 만한 정보
3. 출처: 검색으로 확인된 정확한 URL만 표기

출처 표시 3원칙:
- 원칙 1: 검색 결과에서 확보한 구체적 상세 URL만 사용
- 원칙 2: 상세 URL 없으면 가짜 주소 만들지 않음
- 원칙 3: 출처가 없으면 출처 섹션 자체를 생성하지 않음

예시:

질문: "T90 품질보증 기간은?"
웹 검색: site:kr.sidiz.com T90 품질보증
답변:
시디즈 T90 제품의 품질보증 기간은 3년입니다. 정상 사용 중 발생한 제조상 결함에 대해 무상 수리 서비스를 제공합니다.

출처: kr.sidiz.com/service/warranty
(검색으로 확인된 경우에만)

질문: "지금 예상 배송일은?"
웹 검색: site:kr.sidiz.com 배송 기간
답변:
시디즈 공식 홈페이지에서 주문 시 평균 3-5일 이내 배송됩니다. 제품과 지역에 따라 차이가 있을 수 있습니다.
(정확한 URL을 찾지 못한 경우 출처 생략)

**만약 검색 결과가 없거나 정보를 찾을 수 없다면:**
"죄송합니다. 해당 정보를 공식 홈페이지에서 확인할 수 없습니다. kr.sidiz.com의 고객센터(1588-1857)로 직접 문의하시는 것을 권장드립니다."
"""
    
    else:
        mode_instruction = """
[SEO/GEO 모드 - 검색 최적화 + 증거 기반]

변환 시 다음을 모두 포함하세요:
1. 핵심 검색 키워드 자연스럽게 통합
2. 시디즈 공식 데이터 근거 포함
3. 구조화된 정보
4. 브랜드 톤 유지

출처 표시 3원칙 (매우 중요!):

[원칙 1] 정확성:
- 검색 결과에서 답변의 근거가 된 구체적인 상세 페이지 URL을 확보했을 때만 첨부
- 예: kr.sidiz.com/products/t50 (실제 제품 상세 페이지)
- 예: kr.sidiz.com/faq/view/78 (특정 FAQ 페이지)

[원칙 2] 정직성:
- 직접적인 근거가 되는 상세 URL을 찾지 못했다면:
  * 가짜 주소를 만들지 마세요
  * 메인 홈페이지(kr.sidiz.com)를 고정으로 넣지 마세요
  * 카테고리 메인(kr.sidiz.com/products)도 추측으로 넣지 마세요

[원칙 3] 공백 처리:
- 상세 출처가 없을 때는 '출처' 섹션 자체를 생성하지 마세요
- 출처가 없는 것이 틀린 출처보다 낫습니다

변환 예시:

예시 1 (출처 있음 - 확실한 상세 URL):
원본: "T50 제품 정보"
변환:
시디즈 T50은 3단계 요추 지지 기능을 제공하는 인체공학 의자입니다. 장시간 착석 시 요통 완화에 특화되어 있습니다.

출처: kr.sidiz.com/products/t50

예시 2 (출처 없음 - 일반적인 브랜드 정보):
원본: "편안한 의자"
변환:
시디즈 인체공학 의자는 장시간 착석 시 허리 편안함을 제공하는 사무용 의자로, 척추 건강을 고려한 요추 지지 설계가 특징입니다.

(출처 없음)

예시 3 (출처 없음 - 일반적인 제품 설명):
원본: "게이밍 의자 추천"
변환:
시디즈 게이밍 의자는 장시간 게임 플레이 시에도 요통 완화와 바른 자세 유지를 돕는 인체공학적 설계를 갖추고 있습니다.

(출처 없음)

중요: 정확한 상세 URL이 없다면 출처를 아예 적지 마세요!
"""
    
    return f"""
{base_instruction}

{mode_instruction}

사용자 입력: "{user_input}"

위 입력을 {mode} 모드에 맞춰 변환해줘. 오직 변환된 문구만 출력하고, 부가 설명은 하지 마.
"""

if "mode_selected" not in st.session_state:
    st.session_state.mode_selected = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback_data" not in st.session_state:
    st.session_state.feedback_data = {}

if "feedback_saved" not in st.session_state:
    st.session_state.feedback_saved = set()

if "negative_feedback" not in st.session_state:
    st.session_state.negative_feedback = load_negative_feedback()

if "show_dislike_form" not in st.session_state:
    st.session_state.show_dislike_form = None

if st.session_state.mode_selected is None:
    st.title("✏️ 시디즈 UX 라이팅 가이드")
    st.markdown("### 변환 모드를 선택하세요")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🎨 UX 모드")
        st.info("""
        **브랜드의 감성과 친절함에 집중**
        
        ✨ 사용자 경험 중심의 따뜻한 표현
        ✨ 전문적이면서도 접근하기 쉬운 톤
        ✨ 감성적 연결과 신뢰감 강조
        
        **추천 용도:**
        - 제품 상세 페이지 본문
        - 고객 커뮤니케이션
        - 브랜드 스토리텔링
        """)
        
        if st.button("🎨 UX 모드 선택", type="primary", use_container_width=True):
            st.session_state.mode_selected = "UX"
            st.rerun()
    
    with col2:
        st.markdown("### 🔍 SEO/GEO 모드")
        st.success("""
        **검색 최적화 + 증거 기반 문구**
        
        🔍 핵심 검색 키워드 자연스럽게 포함
        🔍 시디즈 공식 데이터 근거 제시
        🔍 검색엔진/생성형AI 친화적 구조
        🔍 브랜드 톤 유지
        
        **추천 용도:**
        - 메타 디스크립션
        - SEO 제목/설명
        - 제품명 및 카테고리 설명
        """)
        
        if st.button("🔍 SEO/GEO 모드 선택", type="primary", use_container_width=True):
            st.session_state.mode_selected = "SEO/GEO"
            st.rerun()
    
    with col3:
        st.markdown("### 🔎 홈페이지 정보 탐색")
        st.warning("""
        **시디즈 공식 정보 검색**
        
        🔎 제품 스펙 및 품질보증 정보
        🔎 배송 및 AS 안내
        🔎 FAQ 및 고객센터 정보
        🔎 실시간 홈페이지 데이터 기반
        
        **추천 질문:**
        - T90 품질보증 기간은?
        - 지금 예상 배송일은?
        - A/S 신청 방법은?
        """)
        
        if st.button("🔎 홈페이지 탐색 시작", type="primary", use_container_width=True):
            st.session_state.mode_selected = "SEARCH"
            st.rerun()
    
    st.markdown("---")
    st.caption("💡 모드는 언제든 변경할 수 있습니다")
    
    st.stop()

st.title(f"✏️ 시디즈 UX 라이팅 가이드 - {st.session_state.mode_selected} 모드")

col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    if st.button("🔄 모드 변경"):
        st.session_state.mode_selected = None
        st.session_state.messages = []
        st.rerun()

with col2:
    if st.button("🗑️ 대화 초기화"):
        st.session_state.messages = []
        st.session_state.feedback_data = {}
        st.session_state.feedback_saved = set()
        st.rerun()

st.markdown("---")

if len(st.session_state.messages) == 0:
    if st.session_state.mode_selected == "SEARCH":
        mode_emoji = "🔎"
        mode_desc = "시디즈 홈페이지 정보 탐색"
        
        st.info(f"{mode_emoji} **{st.session_state.mode_selected} 모드**: {mode_desc}")
        
        st.markdown("### 💬 궁금한 정보를 질문하세요")
        st.markdown("**예시:**")
        
        col1, col2 = st.columns(2)
        with col1:
            st.code("T90 품질보증 기간은?", language=None)
            st.code("지금 예상 배송일은?", language=None)
        with col2:
            st.code("A/S 신청 방법은?", language=None)
            st.code("가까운 매장 찾기", language=None)
    else:
        mode_emoji = "🎨" if st.session_state.mode_selected == "UX" else "🔍"
        mode_desc = "브랜드 감성 & 친절한 조력자" if st.session_state.mode_selected == "UX" else "검색 최적화 + 증거 기반"
        
        st.info(f"{mode_emoji} **{st.session_state.mode_selected} 모드**: {mode_desc}")
        
        st.markdown("### 💬 변환할 문구를 입력하세요")
        st.markdown("**예시:**")
        
        col1, col2 = st.columns(2)
        with col1:
            st.code("편안한 의자", language=None)
            st.code("허리가 아파요", language=None)
        with col2:
            st.code("T50 의자", language=None)
            st.code("가성비 좋은 의자", language=None)

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        content = message["content"]
        main_text = content
        source_url = None
        
        if "\n출처: " in content:
            parts = content.split("\n출처: ")
            main_text = parts[0]
            source_url = parts[1].strip() if len(parts) > 1 else None
        
        if message["role"] == "assistant":
            # 출처 제외한 본문만 추출
            copy_content = main_text
            safe_text = html.escape(copy_content)
            
            copy_script = """
            <div class="response-container">
                <div style="padding-right: 50px;">""" + main_text + """</div>
                <button class="copy-button" onclick="copyText""" + str(i) + """()" id="copy-btn-""" + str(i) + """" style="opacity: 0.6;">📋</button>
            </div>
            <div id="copy-text-""" + str(i) + """" style="display:none;">""" + safe_text + """</div>
            <script>
            function copyText""" + str(i) + """() {
                const textElement = document.getElementById('copy-text-""" + str(i) + """');
                const text = textElement.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    const btn = document.getElementById('copy-btn-""" + str(i) + """');
                    btn.innerHTML = '✓';
                    setTimeout(() => { btn.innerHTML = '📋'; }, 2000);
                });
            }
            </script>
            """
            
            st.markdown(copy_script, unsafe_allow_html=True)
            
            if source_url:
                if not source_url.startswith("http"):
                    source_url = "https://" + source_url
                display_url = source_url.replace("https://", "").replace("http://", "")
                st.markdown(f'<br>출처: <a href="{source_url}" target="_blank" class="source-link">{display_url}</a>', unsafe_allow_html=True)
            
            # 각 답변마다 피드백 버튼 추가
            st.markdown("<br>", unsafe_allow_html=True)
            
            col1, col2, col_space = st.columns([0.5, 0.5, 5])
            
            with col1:
                if st.button("👍", key=f"like_{i}"):
                    if i not in st.session_state.feedback_saved:
                        original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                        if save_feedback_to_sheet(original, message["content"], 1, st.session_state.mode_selected):
                            st.session_state.feedback_saved.add(i)
                            st.rerun()
            
            with col2:
                if st.button("👎", key=f"dislike_{i}"):
                    st.session_state.show_dislike_form = i
                    st.rerun()
            
            # 싫어요 상세 폼
            if st.session_state.show_dislike_form == i and i not in st.session_state.feedback_saved:
                st.markdown("---")
                st.markdown("#### 📝 피드백을 자세히 알려주세요")
                
                reason = st.selectbox(
                    "싫어요 사유",
                    [
                        "선택하세요",
                        "브랜드 톤이 맞지 않음",
                        "너무 형식적임",
                        "너무 길어요",
                        "너무 짧아요",
                        "키워드가 부족함",
                        "과장된 표현",
                        "원문과 너무 달라짐",
                        "출처가 부적절함",
                        "기타"
                    ],
                    key=f"reason_{i}"
                )
                
                comment = st.text_area(
                    "추가 코멘트 (선택사항)",
                    placeholder="구체적인 피드백을 주시면 더 나은 답변을 만드는 데 도움이 됩니다.",
                    key=f"comment_{i}",
                    height=100
                )
                
                if st.button("📤 제출", key=f"submit_{i}", type="primary"):
                    if reason != "선택하세요":
                        original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                        if save_feedback_to_sheet(original, message["content"], 0, st.session_state.mode_selected, reason, comment):
                            st.success("✅ 상세한 피드백 감사합니다!")
                            st.session_state.feedback_saved.add(i)
                            st.session_state.show_dislike_form = None
                            st.session_state.negative_feedback = load_negative_feedback()
                            st.rerun()
                    else:
                        st.warning("사유를 선택해주세요.")
        else:
            st.markdown(main_text)

# 하단 안내 문구
if len(st.session_state.messages) > 0:
    st.markdown("---")
    st.caption("💡 더 나은 답변을 위한 학습을 위해 피드백을 남겨주세요")

prompt = st.chat_input("변환할 문구를 입력하세요...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            # SEARCH 모드일 때는 웹 검색 활성화된 모델 사용
            if st.session_state.mode_selected == "SEARCH":
                model = get_gemini_model_with_search()
            else:
                model = get_gemini_model()
            
            full_prompt = generate_prompt(
                st.session_state.mode_selected,
                prompt,
                st.session_state.negative_feedback
            )
            
            with st.spinner(f"시디즈 {st.session_state.mode_selected} 톤으로 변환 중..."):
                response = model.generate_content(full_prompt)
                assistant_message = response.text.strip()
            
            st.markdown(assistant_message)
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})
            
        except Exception as e:
            error_str = str(e)
            
            # 상세 에러 로깅
            st.error(f"❌ 오류 발생")
            
            if "429" in error_str or "quota" in error_str.lower():
                st.error("⏱️ **Gemini API 할당량 초과**")
                st.warning("잠시 후 다시 시도해주세요.")
                error_message = "API 할당량이 초과되었습니다. 잠시 후 다시 시도해주세요."
            elif "400" in error_str or "invalid" in error_str.lower():
                st.error("⚠️ **잘못된 요청**")
                st.warning("모델 설정에 문제가 있을 수 있습니다.")
                with st.expander("상세 오류 내용"):
                    st.code(error_str)
                error_message = "일시적으로 서비스를 사용할 수 없습니다."
            elif "500" in error_str or "503" in error_str:
                st.error("🔧 **서버 오류**")
                st.warning("Gemini API 서버에 일시적인 문제가 있습니다.")
                error_message = "일시적으로 서비스를 사용할 수 없습니다."
            else:
                st.error("⚠️ **알 수 없는 오류**")
                with st.expander("상세 오류 내용 (개발자용)"):
                    st.code(error_str)
                    st.code(f"모드: {st.session_state.mode_selected}")
                error_message = "일시적으로 서비스를 사용할 수 없습니다."
            
            st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    st.rerun()

with st.sidebar:
    st.markdown("### 📊 현재 모드")
    mode_emoji = "🎨" if st.session_state.mode_selected == "UX" else "🔍"
    st.info(f"{mode_emoji} **{st.session_state.mode_selected} 모드**")
    
    st.markdown("---")
    
    if st.session_state.feedback_data:
        st.markdown("### 📈 피드백 통계")
        thumbs_up = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 1)
        thumbs_down = sum(1 for f in st.session_state.feedback_data.values() if f["feedback"] == 0)
        total = thumbs_up + thumbs_down
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👍", thumbs_up)
        with col2:
            st.metric("👎", thumbs_down)
        
        if total > 0:
            satisfaction = (thumbs_up / total) * 100
            st.progress(satisfaction / 100)
            st.caption(f"만족도: {satisfaction:.1f}%")
    
    st.markdown("---")
    st.caption("💡 부정 피드백은 자동으로 학습에 반영됩니다")
