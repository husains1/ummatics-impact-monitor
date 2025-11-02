# Contributing to Ummatics Impact Monitor

Thank you for your interest in contributing to the Ummatics Impact Monitor!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/husains1/ummatics-impact-monitor.git
   cd ummatics-impact-monitor
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Start development environment**
   ```bash
   make setup
   # or
   ./setup.sh
   ```

## Code Style

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small
- Use meaningful variable names

Example:
```python
def fetch_twitter_mentions(bearer_token: str, query: str) -> list:
    """
    Fetch Twitter mentions using the Twitter API.
    
    Args:
        bearer_token: Twitter API bearer token
        query: Search query string
        
    Returns:
        List of tweet objects
    """
    # Implementation
```

### JavaScript/React (Frontend)

- Use ESLint for code formatting
- Prefer functional components with hooks
- Use meaningful component and variable names
- Keep components small and focused
- Add PropTypes or TypeScript types

Example:
```javascript
function MetricCard({ title, value, color }) {
  return (
    <div className="metric-card">
      <h3>{title}</h3>
      <p>{value}</p>
    </div>
  )
}
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Examples:
```
feat: add LinkedIn API integration
fix: correct citation count calculation
docs: update API endpoint documentation
refactor: optimize database queries
```

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, documented code
   - Add tests if applicable
   - Update documentation

3. **Test your changes**
   ```bash
   make test-backend
   # or test manually
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: your feature description"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Provide clear description of changes
   - Reference any related issues
   - Ensure all tests pass

## Testing

### Backend Tests

```bash
cd backend
pytest
```

### Frontend Tests

```bash
cd frontend
npm test
```

### Manual Testing

```bash
# Start services
make start

# Run manual ingestion
make ingest

# Check logs
make logs
```

## Database Changes

If you modify the database schema:

1. Update `schema.sql`
2. Create a migration script if needed
3. Document the changes in commit message
4. Test with clean database

Example:
```sql
-- Add new column to citations table
ALTER TABLE citations ADD COLUMN abstract TEXT;
```

## API Changes

When adding or modifying API endpoints:

1. Update `backend/api.py`
2. Update API documentation in README.md
3. Add authentication if needed
4. Test with curl or Postman

Example:
```bash
curl -X GET http://localhost:5000/api/your-endpoint \
  -H "Authorization: Bearer your_token"
```

## Frontend Changes

When modifying the dashboard:

1. Keep components reusable
2. Use Tailwind CSS for styling
3. Ensure responsive design
4. Test on different screen sizes

## Adding New Data Sources

To add a new data source:

1. **Add ingestion function** in `backend/ingestion.py`:
   ```python
   def ingest_new_source():
       """Fetch data from new source"""
       # Implementation
   ```

2. **Update database schema** in `schema.sql`:
   ```sql
   CREATE TABLE new_source_data (
       id SERIAL PRIMARY KEY,
       -- columns
   );
   ```

3. **Add API endpoint** in `backend/api.py`:
   ```python
   @app.route('/api/new-source', methods=['GET'])
   @require_auth
   def get_new_source():
       # Implementation
   ```

4. **Create frontend component** in `frontend/src/App.jsx`:
   ```javascript
   function NewSourceTab({ data }) {
       // Component implementation
   }
   ```

5. **Update documentation** in README.md

## Environment Variables

When adding new configuration:

1. Add to `.env.example` with description
2. Update README.md configuration section
3. Add validation in application code

## Security

- Never commit sensitive data (API keys, passwords)
- Use environment variables for secrets
- Validate and sanitize all inputs
- Follow security best practices

## Questions?

If you have questions or need help:
- Open an issue on GitHub
- Contact: contact@ummatics.org

Thank you for contributing! 🎉
