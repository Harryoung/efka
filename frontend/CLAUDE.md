# Frontend

React + Vite frontend, Admin UI (3000) + User UI (3001).

## Components

```
src/components/
├── ChatView.jsx       # Admin interface
└── UserChatView.jsx   # User interface
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
