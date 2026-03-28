# Contributing

Guidelines for contributing to Tinko.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up development environment (see [Developer Setup](setup.md))
4. Create a new branch for your feature

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write clear, documented code
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation

### 3. Test Your Changes

```bash
# Run tests
uv run pytest

# Check code style
uv run black --check .
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

**Commit Message Format:**

```
type: subject

body (optional)

footer (optional)
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `style:` - Formatting
- `refactor:` - Code refactoring
- `test:` - Tests
- `chore:` - Maintenance

### 5. Push and Create Pull Request

```bash
git push origin feature/my-feature
```

Then create a pull request on GitHub.

## Code Style

### Python

- Follow PEP 8
- Use 4 spaces for indentation
- Max line length: 88 characters (Black default)
- Use type hints
- Write docstrings

### Example

```python
def calculate_average(values: list[float]) -> float:
    """Calculate average of values.
    
    Args:
        values: List of numbers
        
    Returns:
        Average value
        
    Raises:
        ValueError: If values is empty
    """
    if not values:
        raise ValueError("Cannot calculate average of empty list")
    return sum(values) / len(values)
```

## Documentation

- Update README if needed
- Add docstrings to functions
- Update relevant .md files
- Include code examples

## Testing Requirements

- All new features need tests
- Bug fixes should include regression tests
- Tests should pass before merging
- Aim for >80% coverage

## Review Process

1. **Automated Checks**
   - Tests must pass
   - Code style checks
   - Security scans

2. **Manual Review**
   - Code review by maintainer
   - Documentation review
   - Testing on Raspberry Pi

3. **Merge**
   - Squash and merge
   - Clean commit history

## Plugin Contributions

### Submitting a Plugin

1. Create plugin in `plugins/community/`
2. Include README with:
   - Description
   - Installation instructions
   - Hardware requirements
   - Usage examples
3. Add tests
4. Submit PR

### Plugin Guidelines

- Unique namespace (author.pluginname)
- Proper metadata
- Error handling
- GPIO cleanup
- Documentation

## Questions?

- Open an issue on GitHub
- Join discussions
- Check existing documentation

## Code of Conduct

- Be respectful
- Help others
- Give constructive feedback
- Focus on what's best for the project

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## See Also

- [Developer Setup](setup.md)
- [Plugin Tutorial](plugins/tutorial.md)
- [Testing](testing.md)
