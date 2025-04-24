const chatbox = document.getElementById('chatbox');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const loadingIndicator = document.getElementById('loading');
const fileInput = document.getElementById('fileInput');
const fileInfoDiv = document.getElementById('file-info');
const filenameSpan = document.getElementById('filename');
const removeFileButton = document.getElementById('removeFileButton');

let currentFile = null; // Variable to hold the selected file

// Function to escape HTML characters
function escapeHtml(unsafe) {
    // ... (keep the function from previous response) ...
    if (!unsafe) return '';
    return unsafe
         .replace(/&/g, "&")
         .replace(/</g, "<")
         .replace(/>/g, ">")
         .replace(/'/g, "'");
}

// Function to format potential code blocks
function formatCodeBlocks(message) {
    // ... (keep the function from previous response) ...
    const codeBlockRegex = /```python\s*([\s\S]*?)```/g;
    return message.replace(codeBlockRegex, (match, codeContent) => {
        const escapedCode = escapeHtml(codeContent.trim());
        return `<pre><code>${escapedCode}</code></pre>`;
    });
}

// Function to add a message to the chatbox
function addMessage(message, sender) {
    // ... (keep the function from previous response) ...
    const messageWrapper = document.createElement('div');
    messageWrapper.classList.add('message', sender === 'user' ? 'user-message' : 'bot-message');
    const messageContentDiv = document.createElement('div');
    messageContentDiv.classList.add('message-content');
    if (sender === 'bot') {
        messageContentDiv.innerHTML = formatCodeBlocks(message);
    } else {
        messageContentDiv.textContent = message;
    }
    messageWrapper.appendChild(messageContentDiv);
    chatbox.appendChild(messageWrapper);
    chatbox.scrollTop = chatbox.scrollHeight;
}

// --- Function to handle sending message (UPDATED) ---
async function sendMessage() {
    const query = userInput.value.trim();

    // If there's no text query AND no file selected, do nothing or show prompt
    if (!query && !currentFile) {
        addMessage("Please enter a message or upload a file.", 'bot'); // Or just return
        return;
    }

    // Display user query (if any) immediately
    if (query) {
        addMessage(query, 'user');
    }
    // Display file info if a file is being sent
    if (currentFile){
         addMessage(`Uploading file: ${currentFile.name}...`, 'user'); // Indicate file is being sent
    }

    userInput.value = ''; // Clear input field
    loadingIndicator.classList.remove('hidden');
    sendButton.disabled = true;
    userInput.disabled = true;
    fileInput.disabled = true; // Disable file input during processing

    try {
        let response;
        let endpoint;
        let body;
        let headers = {};

        if (currentFile) {
            // --- Send with File ---
            endpoint = '/api/upload_and_chat';
            const formData = new FormData();
            formData.append('file', currentFile); // 'file' must match FastAPI parameter name
            formData.append('query', query);      // 'query' must match FastAPI parameter name
            body = formData;
            // NOTE: Do NOT set Content-Type header when using FormData,
            // the browser sets it correctly including the boundary.
        } else {
            // --- Send Text Only ---
            endpoint = '/api/chat';
            body = JSON.stringify({ query: query });
            headers['Content-Type'] = 'application/json';
        }

        response = await fetch(endpoint, {
            method: 'POST',
            headers: headers, // Empty for FormData, specific for JSON
            body: body,
        });

        // Process response (same logic as before)
        let responseText;
        if (!response.ok) {
            try {
                 const errorData = await response.json();
                 responseText = `Error: ${errorData.detail || response.statusText}`;
            } catch {
                 responseText = `Error: ${response.status} ${response.statusText}`;
            }
             addMessage(responseText, 'bot');
             console.error('Error sending message:', responseText);
        } else {
             const data = await response.json();
             addMessage(data.response, 'bot');
        }

    } catch (error) {
        console.error('Network or other error:', error);
        addMessage(`Sorry, an error occurred: ${error.message}`, 'bot');
    } finally {
         loadingIndicator.classList.add('hidden');
         sendButton.disabled = false;
         userInput.disabled = false;
         fileInput.disabled = false; // Re-enable file input
         removeSelectedFile(); // Clear the selected file after sending
         userInput.focus();
    }
}

// --- File Handling Functions ---
function displayFileInfo(file) {
    if (file) {
        currentFile = file;
        filenameSpan.textContent = file.name;
        fileInfoDiv.classList.remove('hidden');
        userInput.placeholder = "Add an optional message about the file..."; // Update placeholder
    }
}

function removeSelectedFile() {
    currentFile = null;
    fileInput.value = ''; // Clear the file input
    fileInfoDiv.classList.add('hidden');
    filenameSpan.textContent = '';
    userInput.placeholder = "Send a message or upload a file..."; // Reset placeholder
}

// --- Event Listeners ---
sendButton.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
         event.preventDefault();
        sendMessage();
    }
});

// Listener for file input changes
fileInput.addEventListener('change', (event) => {
    const file = event.target.files[0];
    displayFileInfo(file);
});

// Listener for removing the selected file
removeFileButton.addEventListener('click', removeSelectedFile);