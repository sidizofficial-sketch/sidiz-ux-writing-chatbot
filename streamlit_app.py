import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 보안 설정 (대시보드와 동일한 방식)
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 사용 가능한 모델 찾기 (대시보드 로직 그대로)
    model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in model_list if "1.5-flash" in m), model_list[0])
    
    st.success(f"✅ 모델 로드 완료: {target}")
    
except KeyError:
    st.error("❌ Secrets에 'gemini.api_key'가 설정되지 않았습니다.")
    st.info("💡 Streamlit Cloud 설정에서 다음을 추가하세요:")
    st.code("""
[gemini]
api_key = "your_api_key_here"
    """)
    st.stop()
except Exception as e:
    st.error(f"❌ Gemini API 초기화 오류: {e}")
    st.stop()

# ==========================================
# 2. 브랜드 가이드라인
# ==========================================
SYSTEM_INSTRUCTION = """
너는 시디즈의 UX 라이터야. 일반적인 문구를 시디즈만의 [전문적/세심한/혁신적] 톤으로 바꿔줘.
아래는 시디즈 홈페이지에서 가져온 브랜드 문구들이야. 이 말투와 단어 선택을 학습해서 내 문장을 변환해줘.

[참고 문구]
- 시디즈의 디자인은 사용자로부터 시작됩니다
