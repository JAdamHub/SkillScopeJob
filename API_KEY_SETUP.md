# 🔑 Together AI API Key Setup Guide

SkillScopeJob requires a Together AI API key to function. This guide walks you through getting and configuring your API key.

## Why Together AI?

SkillScopeJob uses Together AI's powerful language models for:
- 🤖 Intelligent CV parsing and analysis
- 📊 Job-profile matching and scoring
- 💡 Career improvement recommendations
- 🔍 Skills extraction and categorization

## Getting Your API Key

### Step 1: Create Account

1. Visit [together.ai](https://together.ai)
2. Click "Sign Up" or "Get Started"
3. Create your account (GitHub OAuth available)
4. Verify your email if required

### Step 2: Access API Section

1. Log into your Together AI dashboard
2. Navigate to "API Keys" or "Settings"
3. Look for the API section in the sidebar

### Step 3: Generate API Key

1. Click "Create new API key" or similar button
2. Give your key a descriptive name (e.g., "SkillScopeJob")
3. Copy the generated key (starts with `sk-`)
4. **Important**: Save this key securely - you won't see it again!

### Step 4: Verify Key Format

Your API key should look like this:
```
sk-1234567890abcdef1234567890abcdef1234567890abcdef
```

- Always starts with `sk-`
- Followed by a long string of letters and numbers
- Usually 50+ characters total

## Configuring SkillScopeJob

### For Docker Deployment

1. **Create environment file**:
   ```bash
   cp .env.docker .env
   ```

2. **Edit the .env file**:
   ```bash
   nano .env
   ```

3. **Add your API key**:
   ```bash
   # Together AI API Key (Required)
   TOGETHER_API_KEY=sk-your-actual-api-key-here
   ```

4. **Test your API key** (optional):
   ```bash
   ./test-api-key.sh
   ```

### For Local Development

1. **Set environment variable**:
   ```bash
   export TOGETHER_API_KEY="sk-your-actual-api-key-here"
   ```

2. **Or create .env file**:
   ```bash
   echo "TOGETHER_API_KEY=sk-your-actual-api-key-here" > .env
   ```

## Testing Your Setup

### Using the Test Script

```bash
# Make sure you're in the SkillScopeJob directory
./test-api-key.sh
```

This script will:
- ✅ Verify your .env file exists
- 🔍 Check API key format
- 🧪 Test connection to Together AI
- 📊 Show available models
- 🎉 Confirm everything is working

## Pricing and Limits

### Free Tier
- Together AI typically offers free credits for new users
- Check their website for current free tier limits
- Usually sufficient for testing and small projects

### Paid Plans
- Pay-per-use pricing based on model and tokens
- Different models have different costs
- Check [together.ai/pricing](https://together.ai/pricing) for current rates

### Cost Optimization Tips
- Use smaller models for development/testing
- Choose the right model for your use case
- Monitor your usage in the Together AI dashboard

## Troubleshooting

### Common Issues

#### "API key not found"
- Check your .env file exists
- Verify the format: `TOGETHER_API_KEY=sk-...`
- No quotes needed around the key value

#### "401 Unauthorized"
- Your API key is invalid or expired
- Generate a new key from Together AI dashboard
- Check for typos in the key

#### "403 Forbidden"
- Account might need verification
- Check your Together AI account status
- Verify billing information if on paid plan

#### "Rate limit exceeded"
- You've hit your usage limits
- Wait for the limit to reset
- Consider upgrading your plan

### Getting Help

1. **Together AI Support**: Check their documentation and support channels
2. **SkillScopeJob Issues**: Create an issue on the GitHub repository
3. **API Key Test**: Run `./test-api-key.sh` for diagnostics

## Security Best Practices

### DO ✅
- Keep your API key secure and private
- Use environment variables for API keys
- Regularly rotate your API keys
- Monitor your API usage

### DON'T ❌
- Commit API keys to version control
- Share API keys in screenshots or logs
- Use API keys in client-side code
- Leave unused API keys active

## Sample .env File

```bash
# Together AI API Key (Required)
# Get your key from: https://together.ai
TOGETHER_API_KEY=sk-1234567890abcdef1234567890abcdef1234567890abcdef

# Optional: Custom ports
# MAIN_APP_PORT=8501
# ADMIN_APP_PORT=8502
```

---

**Next Steps**: Once your API key is configured, you're ready to run SkillScopeJob!

- 🐳 **Docker**: Run `./docker-setup.sh`
- 🐍 **Local**: Run `python scripts/setup_database.py` then `streamlit run src/skillscope/ui/main_app.py`
