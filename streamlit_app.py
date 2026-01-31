import streamlit as st
import google.generativeai as genai
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pandas as pd
import time

st.set_page_config(
    page_title="시디즈 UX 라이팅 가이드",
    page_icon="✏️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

def generate_prompt(mode, user_input, negative_feedback):
    """모드별 프롬프트 생성"""
    
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
1. 감성적 연결: 사용자의 감정과 니즈에 공감
2. 친절한 안내: 따뜻하고 접근하기 쉬운 톤
3. 경험 중심: 사용자가 느낄 경험 강조
4. 신뢰감: 과장 없이 진솔한 표현

예시:
"편안한 의자" → "하루 종일 앉아 있어도 지치지 않도록, 당신의 몸을 세심하게 배려한 시팅 경험을 제공합니다"
"""
    
    else:  # SEO/GEO 모드
        mode_instruction = """
[SEO/GEO 모드 - 검색 최적화 + 증거 기반]

포함 요소:
1. 핵심 키워드: 허리 편한 의자, 인체공학 의자, 척추 건강, 요통 완화
2. 데이터 근거: "시디즈 연구소 기반", "20년 노하우", "(kr.sidiz.com)"
3. 명확한 문장: 주어+서술어, 핵심 정보 앞배치
4. 브랜드 톤 유지

예시:
"편안한 의자" → "시디즈 인체공학 의자는 장시간 착석 시 허리 편안함을 제공하는 사무용 의자로, 척추 건강을 고려한 요추 지지 설계가 특징입니다. (kr.sidiz.com)"
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

if "api_call_count" not in st.session_state:
    st.session_state.api_call_count = 0

if "api_call_log" not in st.session_state:
    st.session_state.api_call_log = []

if st.session_state.mode_selected is None:
    st.title("✏️ 시디즈 UX 라이팅 가이드")
    st.markdown("### 변환 모드를 선택하세요")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
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
        
        # 출처 분리
        if "\n출처: " in content:
            parts = content.split("\n출처: ")
            main_text = parts[0]
            source_url = parts[1].strip() if len(parts) > 1 else None
        
        if message["role"] == "assistant":
            # 본문 출력
            st.markdown(main_text)
            
            # 출처가 있으면 한 줄 띄우고 하이퍼링크로 출력
            if source_url:
                if not source_url.startswith("http"):
                    source_url = "https://" + source_url
                st.markdown("")  # 한 줄 공백
                st.markdown(f"📎 출처: [{source_url}]({source_url})")
            
            # 피드백 영역
            st.markdown("")  # 한 줄 공백
            st.caption("💡 더 나은 답변을 위해 피드백을 남겨주세요")
            
            col1, col2, col_space = st.columns([0.8, 0.8, 5])
            
            with col1:
                if st.button("👍 좋아요", key=f"like_{i}"):
                    if i not in st.session_state.feedback_saved:
                        original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                        if save_feedback_to_sheet(original, message["content"], 1, st.session_state.mode_selected):
                            st.session_state.feedback_saved.add(i)
                            st.rerun()
            
            with col2:
                if st.button("👎 싫어요", key=f"dislike_{i}"):
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
            # 사용자 메시지는 그대로 출력
            st.markdown(main_text)

prompt = st.chat_input("변환할 문구를 입력하세요...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            model = get_gemini_model()
            
            full_prompt = generate_prompt(
                st.session_state.mode_selected,
                prompt,
                st.session_state.negative_feedback
            )
            
            # 🔍 API 호출 로깅
            call_time = datetime.now()
            st.session_state.api_call_count += 1
            st.session_state.api_call_log.append({
                "count": st.session_state.api_call_count,
                "time": call_time.strftime("%H:%M:%S"),
                "prompt_length": len(full_prompt)
            })
            
            # ✅ 재시도 제거 - 429 에러는 재시도해도 소용없음!
            with st.spinner(f"시디즈 {st.session_state.mode_selected} 톤으로 변환 중... (API 호출 #{st.session_state.api_call_count})"):
                response = model.generate_content(full_prompt)
                assistant_message = response.text.strip()
                
                st.markdown(assistant_message)
                st.session_state.messages.append({"role": "assistant", "content": assistant_message})
            
        except Exception as e:
            error_str = str(e)
            
            st.error(f"❌ 오류 발생")
            
            if "429" in error_str or "quota" in error_str.lower():
                st.error("⏱️ **API 할당량 초과**")
                
                # 실제 호출 횟수 표시
                st.warning(f"""
                **현재 세션 API 호출: {st.session_state.api_call_count}회**
                
                무료 티어 제한: 분당 15 요청
                
                📌 **가능한 원인:**
                1. 너무 빠르게 연속으로 질문 ({st.session_state.api_call_count}회 호출됨)
                2. 다른 탭/창에서도 동시 사용 중
                3. API 키가 다른 서비스와 공유됨
                
                ⏰ **해결 방법:**
                - 1-2분 대기 후 다시 시도
                - 질문 간격을 5초 이상 두기
                - 새로고침하여 세션 초기화
                """)
                
                with st.expander("🔍 API 호출 로그 확인"):
                    for log in st.session_state.api_call_log[-15:]:
                        st.text(f"#{log['count']} - {log['time']}")
                
                error_message = "API 할당량이 초과되었습니다. 1-2분 후 다시 시도해주세요."
            elif "400" in error_str or "invalid" in error_str.lower():
                st.error("⚠️ **잘못된 요청**")
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
                error_message = "일시적으로 서비스를 사용할 수 없습니다."
            
            st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    st.rerun()

with st.sidebar:
    st.markdown("### 📊 현재 모드")
    mode_emoji = "🎨" if st.session_state.mode_selected == "UX" else "🔍"
    st.info(f"{mode_emoji} **{st.session_state.mode_selected} 모드**")
    
    st.markdown("---")
    
    # 🔍 API 호출 통계 (디버깅용)
    if st.session_state.api_call_count > 0:
        st.markdown("### 🔍 API 호출 통계")
        st.metric("총 호출 횟수", st.session_state.api_call_count)
        
        if st.session_state.api_call_log:
            with st.expander("📋 호출 로그 보기"):
                for log in st.session_state.api_call_log[-10:]:  # 최근 10개만
                    st.text(f"#{log['count']} - {log['time']} ({log['prompt_length']} chars)")
        
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
