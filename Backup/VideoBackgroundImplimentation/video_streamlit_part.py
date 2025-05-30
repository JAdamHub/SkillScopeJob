## VIDEO BACKGROUND START

def load_video_background():
    """Load and display base64 video background with enhanced implementation"""
    try:
        # Check if file exists and get size
        video_file_path = 'background_beige_base64.txt'
        if not os.path.exists(video_file_path):
            st.warning("⚠️ Video background file not found. Using default background.")
            return
        
        file_size = os.path.getsize(video_file_path)
        st.info(f"📹 Loading video background... (File size: {file_size / (1024*1024):.1f} MB)")
        
        # Read the base64 video from file with proper encoding
        with open(video_file_path, 'r', encoding='utf-8') as f:
            video_base64 = f.read().strip()
        
        # Validate base64 content
        if not video_base64:
            st.warning("⚠️ Video file is empty. Using default background.")
            return
        
        if len(video_base64) < 100:
            st.warning("⚠️ Video file appears to be too small. Using default background.")
            return
        
        # Remove any potential data URL prefix if it exists
        if video_base64.startswith('data:video/mp4;base64,'):
            video_base64 = video_base64.replace('data:video/mp4;base64,', '')
        
        st.success(f"✅ Video loaded successfully ({len(video_base64)} characters)")
        
        # Enhanced HTML with video background - using st.markdown for better integration
        video_html = f"""
        <style>
        /* Ensure video background is properly positioned */
        .video-background {{
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            z-index: -1000 !important;
            object-fit: cover !important;
            opacity: 0.2 !important;
            pointer-events: none !important;
        }}
        
        /* Reset Streamlit backgrounds */
        .stApp, .stApp > div, .main, .block-container {{
            background: transparent !important;
        }}
        
        /* Enhanced content styling */
        .main .block-container {{
            background: rgba(255, 255, 255, 0.92) !important;
            border-radius: 12px !important;
            padding: 2rem !important;
            margin: 1rem auto !important;
            backdrop-filter: blur(8px) !important;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
        }}
        
        /* Sidebar enhancements */
        .css-1d391kg, .css-1lcbmhc, .css-17lntkn, section[data-testid="stSidebar"] {{
            background: rgba(255, 255, 255, 0.95) !important;
            backdrop-filter: blur(10px) !important;
        }}
        
        /* Text readability */
        h1, h2, h3, h4, h5, h6 {{
            color: #2c3e50 !important;
            text-shadow: 1px 1px 3px rgba(255,255,255,0.9) !important;
        }}
        
        /* Form and widget backgrounds */
        .stForm, [data-testid="stForm"] {{
            background: rgba(255, 255, 255, 0.85) !important;
            border-radius: 8px !important;
            padding: 1rem !important;
            backdrop-filter: blur(5px) !important;
        }}
        
        /* Expander styling */
        .streamlit-expanderHeader, [data-testid="streamlit-expander-header"] {{
            background: rgba(255, 255, 255, 0.9) !important;
            backdrop-filter: blur(5px) !important;
        }}
        
        .streamlit-expanderContent, [data-testid="streamlit-expander-content"] {{
            background: rgba(255, 255, 255, 0.9) !important;
        }}
        
        /* Metric and info box styling */
        [data-testid="metric-container"] {{
            background: rgba(255, 255, 255, 0.8) !important;
            border-radius: 6px !important;
            backdrop-filter: blur(5px) !important;
        }}
        
        /* Button styling */
        .stButton > button {{
            backdrop-filter: blur(5px) !important;
        }}
        </style>
        
        <div id="video-container">
            <video 
                id="background-video"
                autoplay 
                muted 
                loop 
                playsinline
                class="video-background"
                preload="auto"
                onloadstart="console.log('Video loading started')"
                oncanplay="console.log('Video can play'); this.play().catch(e => console.log('Play failed:', e))"
                onerror="console.error('Video error:', this.error)"
                onloadeddata="console.log('Video data loaded')"
            >
                <source type="video/mp4" src="data:video/mp4;base64,{video_base64}">
                Your browser does not support the video tag.
            </video>
        </div>
        
        <script>
        // Enhanced video handling
        (function() {{
            console.log('Video background script loaded');
            
            function initVideo() {{
                const video = document.getElementById('background-video');
                if (video) {{
                    console.log('Video element found');
                    
                    // Force video properties
                    video.muted = true;
                    video.loop = true;
                    video.autoplay = true;
                    video.playsinline = true;
                    
                    // Try to play
                    const playPromise = video.play();
                    if (playPromise !== undefined) {{
                        playPromise
                            .then(() => {{
                                console.log('Video playing successfully');
                            }})
                            .catch(error => {{
                                console.error('Video play failed:', error);
                                // Try again after a short delay
                                setTimeout(() => {{
                                    video.play().catch(e => console.log('Retry failed:', e));
                                }}, 1000);
                            }});
                    }}
                }} else {{
                    console.log('Video element not found, retrying...');
                    setTimeout(initVideo, 500);
                }}
            }}
            
            // Initialize when DOM is ready
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initVideo);
            }} else {{
                initVideo();
            }}
            
            // Also try after a delay in case Streamlit is still loading
            setTimeout(initVideo, 1000);
        }})();
        </script>
        """
        
        # Use st.markdown with unsafe_allow_html for better integration
        st.markdown(video_html, unsafe_allow_html=True)
        
        # Alternative method using components.html with larger height
        components.html(f"""
        <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -1000; pointer-events: none;">
            <video 
                autoplay muted loop playsinline
                style="width: 100%; height: 100%; object-fit: cover; opacity: 0.4;"
                onloadeddata="this.play().catch(e => console.log('Component video play failed:', e))"
            >
                <source type="video/mp4" src="data:video/mp4;base64,{video_base64}">
            </video>
        </div>
        """, height=0, scrolling=False)
        
        st.success("🎬 Video background loaded and applied!")
        
    except UnicodeDecodeError as e:
        st.error(f"❌ Video file encoding error: {e}")
        st.info("💡 Try saving the base64 file with UTF-8 encoding")
    except MemoryError as e:
        st.error("❌ Video file too large to load in memory")
        st.info("💡 Try using a smaller video file")
    except Exception as e:
        st.error(f"❌ Error loading video background: {e}")
        st.info("💡 Check that the base64 file contains valid video data")
        
        # Show debug info
        with st.expander("🔍 Debug Information"):
            st.write(f"File path: {video_file_path}")
            st.write(f"File exists: {os.path.exists(video_file_path)}")
            if os.path.exists(video_file_path):
                st.write(f"File size: {os.path.getsize(video_file_path)} bytes")
                try:
                    with open(video_file_path, 'r', encoding='utf-8') as f:
                        content_preview = f.read(200)
                        st.write(f"Content preview: {content_preview}...")
                except Exception as preview_e:
                    st.write(f"Could not read file preview: {preview_e}")

# Load video background at the start with error handling
try:
    load_video_background()
except Exception as e:
    st.warning(f"Video background initialization failed: {e}")

## VIDEO BACKGROUND END