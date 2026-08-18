







# Software Design Document (SDD)


## Project: HFT Platform — AI Trading Assistant


| Field              | Value                                    |
| ------------------ | ---------------------------------------- |
| **Document ID**    | SDD-TEAM12-001                           |
| **Version**        | 2.0.0                                    |
| **Date**           | 2026-06-04                               |
| **Status**         | Approved                                 |
| **Authors**        | Team-12 Engineering                      |
| **Classification** | Internal                                 |


---


## 1. Introduction


### 1.1 Purpose


This document describes the software design for the HFT Platform frontend application. It provides a comprehensive architectural overview, component specifications, data flow diagrams, and interface contracts necessary for development, review, and maintenance.


### 1.2 Scope


The application is a single-page React web application that provides a professional high-frequency trading platform interface with an AI-powered assistant for trading insights, latency analysis, risk assessment, and strategy backtesting. This document covers the frontend UI layer only.


### 1.3 Definitions & Acronyms


| Term       | Definition                                       |
| ---------- | ------------------------------------------------ |
| SDD        | Software Design Document                         |
| SPA        | Single Page Application                          |
| UI         | User Interface                                   |
| UX         | User Experience                                  |
| HMR        | Hot Module Replacement                           |
| CSS        | Cascading Style Sheets                           |
| JSX        | JavaScript XML                                   |
| Component  | Reusable, self-contained UI building block       |
| Hook       | React function for state & lifecycle management  |


---


## 2. System Overview


### 2.1 Architecture Style


- **Pattern:** Component-Based Architecture (CBA)
- **Framework:** React 19 with Vite 8
- **State Management:** React Hooks (`useState`, `useCallback`, `useRef`, `useEffect`, `useMemo`)
- **Styling:** CSS with BEM naming + CSS Custom Properties (40+ design tokens)
- **Theming:** Dual dark/light theme via `data-theme` attribute + localStorage
- **Build Tool:** Vite (ESBuild + Rollup)


### 2.2 High-Level Architecture


```
┌─────────────────────────────────────────────────┐
│                   Browser                       │
│  ┌───────────────────────────────────────────┐  │
│  │              React Application            │  │
│  │  ┌─────────┐  ┌────────────────────────┐  │  │
│  │  │ Sidebar │  │     Main Chat Area     │  │  │
│  │  │(collaps)│  │  ┌──────────────────┐  │  │  │
│  │  │ • Brand │  │  │   ChatHeader     │  │  │  │
│  │  │ • New   │  │  │  (theme toggle)  │  │  │  │
│  │  │   Chat  │  │  ├──────────────────┤  │  │  │
│  │  │ • Conv  │  │  │   ChatWindow     │  │  │  │
│  │  │   List  │  │  │  ┌────────────┐  │  │  │  │
│  │  │ • Col-  │  │  │  │  Messages  │  │  │  │  │
│  │  │  lapse  │  │  │  │  Bubbles   │  │  │  │  │
│  │  │   Btn   │  │  │  └────────────┘  │  │  │  │
│  │  │         │  │  ├──────────────────┤  │  │  │
│  │  │         │  │  │   ChatInput      │  │  │  │
│  │  └─────────┘  │  └──────────────────┘  │  │  │
│  │               └────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```


---


## 3. Component Specification


### 3.1 Component Hierarchy


```
App (useTheme, sidebarCollapsed state)
├── Sidebar (collapsible)
│   ├── BrandHeader (logo + title)
│   ├── NewChatButton
│   ├── ConversationList
│   └── CollapseButton
├── ChatLayout
│   ├── ChatHeader (theme toggle, latency badge)
│   ├── ChatWindow
│   │   ├── WelcomeScreen (HFT branded)
│   │   ├── MessageBubble (user)
│   │   │   └── Avatar
│   │   ├── MessageBubble (assistant)
│   │   │   └── Avatar
│   │   └── TypingIndicator
│   └── ChatInput
```


### 3.2 Component Details


#### 3.2.1 `App` (Root)


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| Application shell, state orchestration    |
| **State**         | conversations[], activeId, sidebarCollapsed, theme |
| **Children**      | Sidebar, ChatLayout                       |


#### 3.2.2 `Sidebar`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| Conversation history, navigation          |
| **Props**         | conversations, activeId, onSelect,        |
|                   | onNewChat, collapsed, onToggleCollapse    |
| **Behavior**      | Collapsible to icon-only, lists all chats |


#### 3.2.3 `ChatHeader`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| Display bot identity, status, controls    |
| **Props**         | theme, onToggleTheme, onToggleSidebar     |
| **Behavior**      | Shows bot name, online status, latency    |
|                   | badge, sun/moon theme toggle button       |


#### 3.2.4 `ChatWindow`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| Scrollable message container              |
| **Props**         | messages[], isTyping                      |
| **Behavior**      | Auto-scrolls to latest, renders welcome   |
|                   | screen when empty                         |


#### 3.2.5 `MessageBubble`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| Single message rendering                  |
| **Props**         | message { role, content, timestamp }      |
| **Behavior**      | Different alignment/style per role        |


#### 3.2.6 `ChatInput`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| User text input & send action             |
| **Props**         | onSend, disabled                          |
| **Behavior**      | Auto-resize textarea, Enter to send,      |
|                   | Shift+Enter for newline                   |


#### 3.2.7 `WelcomeScreen`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| Empty state with suggested prompts        |
| **Props**         | onSuggestionClick                         |
| **Behavior**      | Displays greeting and clickable prompts   |


#### 3.2.8 `TypingIndicator`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| Animated "bot is typing" indicator        |
| **Props**         | (none)                                    |
| **Behavior**      | Three-dot bounce animation                |


#### 3.2.9 `Avatar`


| Property          | Value                                     |
| ----------------- | ----------------------------------------- |
| **Responsibility**| User/bot avatar display                   |
| **Props**         | role ('user' | 'assistant')               |
| **Behavior**      | Renders icon based on role                |


---


## 4. Data Model


### 4.1 Message Object


```javascript
{
 id: string,          // UUID
 role: 'user' | 'assistant',
 content: string,
 timestamp: number    // Unix epoch ms
}
```


### 4.2 Conversation Object


```javascript
{
 id: string,          // UUID
 title: string,       // First user message (truncated)
 messages: Message[],
 createdAt: number,
 updatedAt: number
}
```


---


## 5. State Management


### 5.1 Custom Hook: `useChat`


```
┌──────────────────────────────────────────────┐
│                  useChat()                   │
├──────────────────────────────────────────────┤
│ State:                                       │
│  • conversations: Conversation[]             │
│  • activeConversationId: string | null       │
│  • isTyping: boolean                         │
├──────────────────────────────────────────────┤
│ Computed:                                    │
│  • activeConversation: Conversation | null   │
│  • messages: Message[]                       │
├──────────────────────────────────────────────┤
│ Actions:                                     │
│  • sendMessage(content: string): void        │
│  • createNewChat(): void                     │
│  • selectConversation(id: string): void      │
│  • deleteConversation(id: string): void      │
└──────────────────────────────────────────────┘
```


### 5.2 Message Flow


```
User Input → sendMessage() → Add user message → Set isTyping=true
   → Simulate bot delay (1-2s) → Add bot response → Set isTyping=false
```


---


## 6. UI/UX Design Specifications


### 6.1 Design Tokens (CSS Custom Properties)


| Token                    | Dark Value     | Light Value    | Purpose              |
| ------------------------ | -------------- | -------------- | -------------------- |
| `--color-bg-primary`    | `#0a0e17`       | `#f8f9fc`       | Main background      |
| `--color-bg-secondary`  | `#0d1220`       | `#ffffff`       | Sidebar background   |
| `--color-bg-chat`       | `#0f1629`       | `#f0f2f8`       | Chat area background |
| `--color-accent`        | `#00d4ff`       | `#4f46e5`       | Primary accent       |
| `--color-text-primary`  | `#e2e8f0`       | `#1a1a2e`       | Primary text         |
| `--color-text-secondary`| `rgba(255,.5)`  | `#6b7280`       | Secondary text       |
| `--color-user-bubble`   | gradient        | gradient        | User message bg      |
| `--color-bot-bubble`    | `#141a28`       | `#ffffff`       | Bot message bg       |
| `--radius-sm`           | `8px`           | Small border radius  |
| `--radius-md`           | `12px`          | Medium border radius |
| `--radius-lg`           | `20px`          | Large border radius  |
| `--shadow-sm`           | `0 1px 3px...`  | Subtle shadow        |


### 6.2 Responsive Breakpoints


| Breakpoint | Width      | Layout                       |
| ---------- | ---------- | ---------------------------- |
| Mobile     | < 768px    | Sidebar overlay, full chat   |
| Tablet     | 768–1024px | Narrow sidebar + chat        |
| Desktop    | > 1024px   | Full sidebar (280px) + chat  |


### 6.3 Animations


| Element          | Animation          | Duration | Easing          |
| ---------------- | ------------------ | -------- | --------------- |
| Message appear   | Fade + slide up    | 300ms    | ease-out        |
| Typing dots      | Bounce sequence    | 1.4s     | ease-in-out     |
| Sidebar toggle   | Slide left/right   | 250ms    | ease            |
| Button hover     | Scale + shadow     | 150ms    | ease            |


---


## 7. File Structure


```
team-12/
├── docs/
│   └── SDD.md                          # This document
├── public/
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── Avatar/
│   │   │   ├── Avatar.jsx
│   │   │   └── Avatar.css
│   │   ├── ChatHeader/
│   │   │   ├── ChatHeader.jsx
│   │   │   └── ChatHeader.css
│   │   ├── ChatInput/
│   │   │   ├── ChatInput.jsx
│   │   │   └── ChatInput.css
│   │   ├── ChatLayout/
│   │   │   ├── ChatLayout.jsx
│   │   │   └── ChatLayout.css
│   │   ├── ChatWindow/
│   │   │   ├── ChatWindow.jsx
│   │   │   └── ChatWindow.css
│   │   ├── MessageBubble/
│   │   │   ├── MessageBubble.jsx
│   │   │   └── MessageBubble.css
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.jsx
│   │   │   └── Sidebar.css
│   │   ├── TypingIndicator/
│   │   │   ├── TypingIndicator.jsx
│   │   │   └── TypingIndicator.css
│   │   └── WelcomeScreen/
│   │       ├── WelcomeScreen.jsx
│   │       └── WelcomeScreen.css
│   ├── hooks/
│   │   ├── useChat.js
│   │   └── useTheme.js
│   ├── utils/
│   │   └── formatTime.js
│   ├── constants/
│   │   └── botResponses.js
│   ├── App.jsx
│   ├── App.css
│   ├── index.css
│   └── main.jsx
├── .gitignore
├── index.html
├── package.json
├── vite.config.js
├── eslint.config.js
└── README.md
```


---


## 8. Security Considerations


| Concern              | Mitigation                                        |
| -------------------- | ------------------------------------------------- |
| XSS in messages      | React auto-escapes JSX output; no `dangerouslySetInnerHTML` |
| Input validation     | Client-side trimming; empty message prevention     |
| Dependency supply chain | Lock file committed; `npm audit` in CI          |


---


## 9. Testing Strategy


| Level       | Tool            | Coverage Target |
| ----------- | --------------- | --------------- |
| Unit        | Vitest + RTL    | Components      |
| Integration | Vitest          | useChat hook    |
| E2E         | Playwright      | Critical paths  |


> **Note:** Testing infrastructure will be added in a subsequent milestone.


---


## 10. Deployment


| Environment | URL               | Build Command    |
| ----------- | ----------------- | ---------------- |
| Development | localhost:5173    | `npm run dev`    |
| Production  | TBD               | `npm run build`  |


---


## 11. Revision History


| Version | Date       | Author             | Changes          |
| ------- | ---------- | ------------------ | ---------------- |
| 1.0.0   | 2026-06-04 | Team-12 Engineering| Initial release  |
