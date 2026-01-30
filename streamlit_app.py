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

# ===================
