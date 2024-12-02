# SASK-ATPROTO-DJANGO

A Django implementation of an AT Protocol custom feed generator designed to aggregate and filter Saskatchewan-related content from the Bluesky social network.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Docker (optional for containerized deployment)
- pip or pipenv for dependency management

### Dependencies Management

This project uses both `pipenv` and traditional `requirements.txt` for flexibility in dependency management.

#### Using pipenv (Recommended)
```bash
# Install pipenv if you haven't already
pip install pipenv

# Install dependencies
pipenv install

# Activate the virtual environment
pipenv shell
```

#### Using pip
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Setup

1. Copy the example environment file:
```bash
cp example.env .env
```

2. Update the `.env` file with your configuration:
```env
# Required settings
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
BLUESKY_HANDLE=your-handle.bsky.social
BLUESKY_APP_PASSWORD=your-app-password

# Optional settings
DEBUG=True
SECRET_KEY=your-secret-key
```

## 🛠️ Running the Services

### Development Server
```bash
# Apply database migrations
python manage.py migrate

# Run the development server
python manage.py runserver
```

### Running the Feed Generator
```bash
# Start the feed ingestion process
python manage.py start_feed <service_uri> --algorithm=<algorithm_name>

# Examples:
# For Flatlanders feed:
python manage.py start_feed wss://bsky.social --algorithm=flatlanders

# For logging only:
python manage.py start_feed wss://bsky.social --algorithm=logger
```

### Content Labeler
```bash
# Start the content labelling service
python manage.py start_labeler
```

### Docker Deployment
```bash
# Build the Docker image
docker build -t sask-atproto .

# Run the container
docker run -p 8000:8000 --env-file .env sask-atproto
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test files
pytest tests/flatlanders/test_views.py

# Run with coverage report
pytest --cov=.
```

## 📦 Project Structure

The project is organized into several key components:

- `firehose/`: Handles Bluesky firehose connection and data ingestion
- `flatlanders/`: Core feed algorithm implementation and content filtering
- `sk_atp_feed/`: Main Django project configuration
- For complete structure, see [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create your feature branch:
```bash
git checkout -b feature/amazing-feature
```

3. Set up your development environment following the steps above

4. Make your changes and ensure:
   - All tests pass (`pytest`)
   - Code follows PEP 8 style guide
   - New features include appropriate tests
   - Documentation is updated as needed

5. Commit your changes:
```bash
git commit -m 'Add amazing feature'
```

6. Push to your branch:
```bash
git push origin feature/amazing-feature
```

7. Open a Pull Request

### Coding Standards

- Follow PEP 8 guidelines
- Include docstrings for all functions and classes
- Write meaningful commit messages
- Add tests for new functionality
- Update documentation as needed

## 📝 License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

## 🚧 Known Issues and Limitations

- Currently supports single-instance deployment only
- Rate limiting on the Bluesky API may affect feed updates
- Content labelling is optimized for English language posts

## 🔗 Additional Resources

- [AT Protocol Documentation](https://atproto.com/docs)
- [Django Documentation](https://docs.djangoproject.com/)
- [Bluesky API Documentation](https://github.com/bluesky-social/atproto/tree/main/packages/api)

Made with ❤️ for the Saskatchewan Bluesky community
