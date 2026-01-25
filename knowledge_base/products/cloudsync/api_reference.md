# CloudSync Pro API Reference

## Authentication

All API requests require Bearer token authentication.

```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
     https://api.cloudsync.techcorp.com/v2/files
```

### Token Lifecycle
- Access token validity: 1 hour
- Refresh token validity: 30 days
- Rate limit: 10,000 requests/hour per token

## Endpoints

### Files API

#### List Files
```
GET /v2/files
```

Query Parameters:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| folder_id | string | No | Parent folder ID (root if empty) |
| limit | integer | No | Max 100, default 50 |
| cursor | string | No | Pagination cursor |

Response:
```json
{
  "files": [
    {
      "id": "file_abc123",
      "name": "report.pdf",
      "size": 1048576,
      "modified": "2024-05-20T10:30:00Z",
      "type": "file"
    }
  ],
  "cursor": "next_page_token",
  "has_more": true
}
```

#### Upload File
```
POST /v2/files/upload
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | binary | Yes | File content |
| folder_id | string | No | Destination folder |
| overwrite | boolean | No | Overwrite if exists |

**Size Limits:**
- Single file: 5GB max
- Chunk size for resumable: 10MB

### Webhooks

Configure webhooks in dashboard or via API:

```
POST /v2/webhooks
```

```json
{
  "url": "https://your-server.com/webhook",
  "events": ["file.created", "file.deleted", "file.shared"],
  "secret": "your_webhook_secret"
}
```

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 401 | Unauthorized | Invalid or expired token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 429 | Rate Limited | Exceeded 10,000 req/hour |
| 500 | Internal Error | Contact support |

## SDK Examples

### Python
```python
from cloudsync import Client

client = Client(api_key="YOUR_KEY")
files = client.files.list(folder_id="root")
for f in files:
    print(f.name, f.size)
```

### JavaScript
```javascript
import { CloudSync } from '@techcorp/cloudsync';

const client = new CloudSync({ apiKey: 'YOUR_KEY' });
const files = await client.files.list({ folderId: 'root' });
files.forEach(f => console.log(f.name, f.size));
```
