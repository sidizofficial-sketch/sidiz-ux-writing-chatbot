import streamlit as st
import google.generativeai as genai
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import pandas as pd

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="시디즈 UX 라이팅 가이드",
    page_icon="✏️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. Google Sheets 설정
# ==========================================
def get_gsheet_client():
    """Google Sheets 클라이언트 초기화"""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Google Sheets 연동 오류: {e}")
        return None

def save_feedback_to_sheet(original_text, converted_text, feedback, mode):
    """피드백을 Google Sheets에 저장"""
    try:
        client = get_gsheet_client()
        if client is None:
            return False
        
        sheet_url = st.secrets.get("feedback_sheet_url", "")
        if not sheet_url:
            return False
        
        sheet = client.open_by_url(sheet_url).sheet1
        
        # 헤더 확인
        if sheet.row_count == 0 or sheet.cell(1, 1).value != "시간":
            sheet.insert_row(["시간", "모드", "원본 문구", "변환된 문구", "피드백", "피드백값"], 1)
        
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            mode,
            original_text,
            converted_text,
            "👍" if feedback == 1 else "👎",
            feedback
        ]
        
        sheet.append_row(row)
        return True
        
    except Exception as e:
        st.error(f"저장 오류: {e}")
        return False

def load_negative_feedback():
    """부정 피드백 로드 (Negative Prompt 생성)"""
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
        
        # 부정 피드백만 필터링
        negative_df = df[df['피드백값'] == 0]
        
        if negative_df.empty:
            return ""
        
        # Negative Prompt 생성
        negative_examples = ""
        for _, row in negative_df.tail(10).iterrows():  # 최근 10개만
            negative_examples += f"""
원본: "{row['원본 문구']}"
나쁜 변환: "{row['변환된 문구']}" ← 이런 스타일 피하기
"""
        
        return f"""
[사용자가 싫어한 변환 스타일 - 절대 사용 금지 ❌]
{negative_examples}
"""
        
    except Exception as e:
        return ""

# ==========================================
# 3. Gemini API 설정
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
except KeyError as e:
    st.error(f"❌ Secrets 설정 오류: {e}")
    st.stop()

# ==========================================
# 4. 모델 초기화
# ==========================================
@st.cache_resource
def get_gemini_model():
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    return genai.GenerativeModel(target)

# ==========================================
# 5. 프롬프트 생성 함수
# ==========================================
def generate_prompt(mode, user_input, negative_feedback):
    """모드별 프롬프트 생성"""
    
    # 공통 베이스 (Google AI Studio에 이미 학습된 가이드 활용)
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
1. **감성적 연결**: 사용자의 감정과 니즈에 공감하는 표현
2. **친절한 안내**: 전문적이되 따뜻하고 접근하기 쉬운 톤
3. **경험 중심**: 제품의 스펙보다 사용자가 느낄 경험을 강조
4. **신뢰감**: 과장 없이 진솔하고 믿을 수 있는 표현

변환 예시:
원본: "편안한 의자"
변환: "하루 종일 앉아 있어도 지치지 않도록, 당신의 몸을 세심하게 배려한 시팅 경험을 제공합니다"

원본: "허리 아픔"
변환: "척추의 자연스러운 곡선을 존중하여, 장시간 착석에도 편안한 자세를 유지할 수 있도록 설계했습니다"

원본: "고급스러운 디자인"
변환: "공간의 품격을 높이는 세련된 디자인으로, 당신의 일상에 프리미엄 경험을 더합니다"
"""
    
    else:  # SEO/GEO 모드
        mode_instruction = """
[SEO/GEO 모드 - 검색 최적화 + 증거 기반]

변환 시 다음을 모두 포함하세요:
1. **핵심 검색 키워드**: 자연스럽게 통합
   - 허리 편한 의자, 인체공학 의자, 사무용 의자, 게이밍 의자
   - 척추 건강, 요통 완화, 장시간 착석, 바른 자세
   
2. **시디즈 공식 데이터 근거**: 가능하면 수치나 사실을 포함
   - "시디즈 연구소의 인체공학 연구 기반"
   - "20년 이상의 의자 제조 노하우"
   - "(kr.sidiz.com)" 출처 표기
   
3. **구조화된 정보**: 검색엔진이 이해하기 쉬운 명확한 문장
   - 주어 + 서술어 명확
   - 핵심 정보를 문장 앞부분에 배치
   - 한 문장 = 하나의 핵심 메시지
   
4. **브랜드 톤 유지**: SEO를 위해 브랜드 감성을 잃지 않음

변환 예시:
원본: "편안한 의자"
변환: "시디즈 인체공학 의자는 장시간 착석 시 허리 편안함을 제공하는 사무용 의자로, 척추 건강을 고려한 요추 지지 설계가 특징입니다. 20년 이상의 노하우로 개발된 시팅 솔루션입니다. (kr.sidiz.com)"

원본: "게이밍 의자"
변환: "시디즈 게이밍 의자는 장시간 게임 플레이 시에도 요통 완화와 바른 자세 유지를 돕는 인체공학적 설계를 갖추고 있습니다. 오피스 시팅 전문 브랜드의 연구 기반 설계로 프로게이머의 퍼포먼스를 지원합니다. (kr.sidiz.com)"

원본: "허리 아파요"
변환: "허리 통증 완화에 도움이 되는 시디즈 인체공학 의자는 척추 건강을 위한 요추 지지 기능과 체압 분산 설계를 적용했습니다. 장시간 착석 시에도 편안한 자세 유지가 가능합니다. (kr.sidiz.com)"
"""
    
    final_prompt = f"""
{base_instruction}

{mode_instruction}

사용자 입력: "{user_input}"

위 입력을 {mode} 모드에 맞춰 변환해줘. 오직 변환된 문구만 출력하고, 부가 설명은 하지 마.
"""
    
    return final_prompt

# ==========================================
# 6. 세션 상태 초기화
# ==========================================
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

# ==========================================
# 7. 모드 선택 화면
# ==========================================
if st.session_state.mode_selected is None:
    st.title("💺 시디즈 UX 라이팅 도구")
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
        - 상품명 및 카테고리 설명
        """)
        
        if st.button("🔍 SEO/GEO 모드 선택", type="primary", use_container_width=True):
            st.session_state.mode_selected = "SEO/GEO"
            st.rerun()
    
    st.markdown("---")
    st.caption("💡 모드는 언제든 변경할 수 있습니다")
    
    st.stop()

# ==========================================
# 8. 메인 UI (모드 선택 후)
# ==========================================
st.title(f"💺 시디즈 UX 라이팅 도구 - {st.session_state.mode_selected} 모드")

# 모드 변경 버튼
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

# ==========================================
# 9. 초기 안내 메시지
# ==========================================
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
        st.code("고급스러운 디자인", language=None)
        st.code("가성비 좋은 의자", language=None)

# ==========================================
# 10. 대화 내역 표시
# ==========================================
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # 피드백 버튼 (마지막 assistant 메시지에만)
        if message["role"] == "assistant" and i == len(st.session_state.messages) - 1:
            st.markdown("---")
            st.markdown("**이 답변이 도움이 되었나요?**")
            
            col1, col2, col3 = st.columns([1, 1, 4])
            
            with col1:
                if st.button("👍 좋아요", key=f"like_{i}"):
                    if i not in st.session_state.feedback_saved:
                        st.session_state.feedback_data[i] = {
                            "message": message["content"],
                            "feedback": 1,
                            "prompt": st.session_state.messages[i-1]["content"] if i > 0 else ""
                        }
                        
                        original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                        if save_feedback_to_sheet(original, message["content"], 1, st.session_state.mode_selected):
                            st.success("✅ 피드백 감사합니다!")
                            st.session_state.feedback_saved.add(i)
                            st.rerun()
            
            with col2:
                if st.button("👎 싫어요", key=f"dislike_{i}"):
                    if i not in st.session_state.feedback_saved:
                        st.session_state.feedback_data[i] = {
                            "message": message["content"],
                            "feedback": 0,
                            "prompt": st.session_state.messages[i-1]["content"] if i > 0 else ""
                        }
                        
                        original = st.session_state.messages[i-1]["content"] if i > 0 else ""
                        if save_feedback_to_sheet(original, message["content"], 0, st.session_state.mode_selected):
                            st.warning("👎 피드백이 저장되었습니다. 다음 답변부터 개선하겠습니다!")
                            st.session_state.feedback_saved.add(i)
                            # 부정 피드백 즉시 반영
                            st.session_state.negative_feedback = load_negative_feedback()
                            st.rerun()

# ==========================================
# 11. 사용자 입력 처리
# ==========================================
prompt = st.chat_input("변환할 문구를 입력하세요...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            model = get_gemini_model()
            
            # 프롬프트 생성
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
            
            if "429" in error_str or "quota" in error_str.lower():
                st.error("⏱️ **Gemini API 할당량 초과**")
                st.warning("잠시 후 다시 시도해주세요.")
            else:
                st.error(f"❌ 오류: {error_str}")
            
            error_message = "일시적으로 서비스를 사용할 수 없습니다."
            st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    st.rerun()

# ==========================================
# 12. 사이드바 통계
# ==========================================
with st.sidebar:
    st.markdown(f"### 📊 현재 모드")
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
