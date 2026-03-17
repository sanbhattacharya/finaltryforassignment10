### Task 1A: Page Setup & API Connection
**Prompt:** "Help me with step 1. Part A: Page Setup & API Connection (20 points)
Requirements:

Use st.set_page_config(page_title="My AI Chat", layout="wide").
Load your Hugging Face token using st.secrets["HF_TOKEN"]. The token must never be hardcoded in app.py.
If the token is missing or empty, display a clear error message in the app. The app must not crash.
Send a single hardcoded test message (e.g. "Hello!") to the Hugging Face API using the loaded token and display the model’s response in the main area.
Handle API errors gracefully (missing token, invalid token, rate limit, network failure) with a user-visible message rather than a crash.
Success criteria (Part A): Running streamlit run app.py with a valid .streamlit/secrets.toml sends a test message and displays the model’s reply. Running it without the secrets file shows an error message instead of crashing."
**AI Suggestion:** Suggested using st.secrets.get("HF_TOKEN") combined with an if not hf_token: st.error(...) block to prevent the app from crashing.
**My Modifications & Reflections:** The code worked perfectly. I made sure to place the token check at the very beginning of the main() function so no other logic runs if the credentials are missing.

### Task 1B: Multi-Turn Conversation UI
**Prompt:** "Here is Part B: Multi-Turn Conversation UI (30 points)
Requirements:

Extend Part A to replace the hardcoded test message with a real input interface.
Use native Streamlit chat UI elements. Render messages with st.chat_message(...) and collect user input with st.chat_input(...).
Add a fixed input bar at the bottom of the main area.
Store the full conversation history in st.session_state. After each exchange, append both the user message and the assistant response to the history.
Send the full message history with each API request so the model maintains context.
Render the conversation history above the input bar using default Streamlit UI elements rather than CSS-based custom chat bubbles.
The message history must scroll independently of the input bar — the input bar stays visible at all times.
Success criteria (Part B): Sending multiple messages in a row produces context-aware replies (e.g. the model remembers the user’s name from an earlier message). Messages are displayed with correct styling and the input bar remains fixed.

"
**AI Suggestion:** Suggested a render_history function that loops through st.session_state.history and uses st.chat_message to display roles.
**My Modifications & Reflections:** I adapted this to use a dictionary format {"role": "...", "content": "..."} for messages, which is exactly what the Hugging Face API expects, making the API call much cleaner.

### Task 1C: Chat Management
**Prompt:** "Part C: Chat Management (25 points)
Requirements:

Add a New Chat button to the sidebar that creates a fresh, empty conversation and adds it to the sidebar chat list.
Use the native Streamlit sidebar (st.sidebar) for chat navigation.
The sidebar shows a scrollable list of all current chats, each displaying a title and timestamp.
The currently active chat must be visually highlighted in the sidebar.
Clicking a chat in the sidebar switches to it without deleting or overwriting any other chats.
Each chat entry must have a ✕ delete button. Clicking it removes the chat from the list. If the deleted chat was active, the app must switch to another chat or show an empty state.
Success criteria (Part C): Multiple chats can be created, switched between, and deleted independently. The active chat is always visually distinct."
**AI Suggestion:** Suggested using st.sidebar.columns to place the chat selection button and the delete button (✕) side-by-side.
**My Modifications & Reflections:** I added a visual indicator (➡️) to the active chat's label so it satisfies the "visually distinct" requirement without needing custom CSS.

### Task 1D: Chat Persistence
**Prompt:** "Part D: Chat Persistence (25 points)
Requirements:

Each chat session is saved as a separate JSON file inside a chats/ directory. Each file must store at minimum: a chat ID, a title or timestamp, and the full message history.
On app startup, all existing files in chats/ are loaded and shown in the sidebar automatically.
Returning to a previous chat and continuing the conversation must work correctly.
Deleting a chat (✕ button) must also delete the corresponding JSON file from chats/.
A generated or summarized chat title is acceptable and encouraged. The title does not need to be identical to the first user message.
Success criteria (Part D): Closing and reopening the app shows all previous chats intact in the sidebar. Continuing a loaded chat works correctly. Deleting a chat removes its file from disk.

"
**AI Suggestion:** Recommended using the os and json libraries to create a persist_chat function that writes to f"{chat_id}.json".
**My Modifications & Reflections:** I had to ensure os.makedirs(CHATS_DIR, exist_ok=True) was called at the start to avoid errors if the chats/ folder didn't exist yet. It works great across app restarts.

### Task 2: Response streaming
**Prompt:** "[Task 2: Response Streaming (20 points)
Goal: Display the model’s reply token-by-token as it is generated instead of waiting for the full response.

Requirements
Use the stream=True parameter in your API request and handle the server-sent event stream.
In Streamlit, use native Streamlit methods such as st.write_stream() or manually update a placeholder with st.empty() as chunks arrive.
The full streamed response must be saved to the chat history once streaming is complete.
Hint: Add stream=True to your request payload and set stream=True on the requests.post() call. The response body will be a series of data: lines in SSE format.

Note: Very small models such as meta-llama/Llama-3.2-1B-Instruct may stream so quickly that the output appears to arrive all at once. If your app is correctly receiving multiple streamed chunks but the effect is too fast to notice, you are required to add a very short delay between rendering chunks so the streaming behavior is visible in the UI.

Success criteria: Responses appear incrementally in the chat interface and are correctly saved to history.]"
**AI Suggestion:** Provided a generator function using response.iter_lines() to parse the "data: " chunks from the API.
**My Modifications & Reflections:** I added time.sleep(0.05) as suggested because the Llama-3.2-1B model was streaming too fast to see. Now it has that cool "typing" effect.

### Task 3: User memory
**Prompt:** "Task 3: User Memory (20 points)
Goal: Extract and store user preferences from conversations, then use them to personalize future responses.

Requirements
After each assistant response, make a second lightweight API call asking the model to extract any personal traits or preferences mentioned by the user in that message.
Extracted traits are stored in a memory.json file. Example categories might include name, preferred language, interests, communication style, favorite topics, or other useful personal preferences.
The sidebar displays a User Memory expander panel showing the currently stored traits.
Include a native Streamlit control to clear/reset the saved memory.
Stored memory is injected into the system prompt of future conversations so the model can personalize responses.
Implementation note: The categories above are only examples for reference. It is up to you to decide what traits to store, how to structure your memory.json, how to merge or update existing memory, and how to incorporate that memory into future prompts, as long as the final app clearly demonstrates persistent user memory and personalization.

Hint: A simple memory extraction prompt might look like: “Given this user message, extract any personal facts or preferences as a JSON object. If none, return {}”

Success criteria: User traits are extracted, displayed in the sidebar, and used to personalize subsequent responses."
**AI Suggestion:** Suggested a second "lightweight" API call with a specific system prompt to extract facts as a JSON object.
**My Modifications & Reflections:** I combined this with a build_system_message function that automatically appends the stored preferences to the AI's instructions, making the assistant actually remember my name and interests.