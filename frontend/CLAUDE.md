# Frontend

React + Vite 前端，Admin UI (3000) + User UI (3001)。

## Components

```
src/components/
├── ChatView.jsx       # Admin 界面
└── UserChatView.jsx   # User 界面
```

## Manual Start

```bash
npm run dev                                        # Admin :3000
VITE_APP_MODE=user npm run dev -- --port 3001     # User :3001
```

## Dependencies

```bash
npm install
```
