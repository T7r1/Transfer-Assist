const express = require('express');
const cors = require('cors');
const Anthropic = require('@anthropic-ai/santhropic');

const app = express();
const port = 3000;

app.use(cors());
app.use(express.json());

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || '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'
});

app.post('/api/anthropic', async (req, res) => {
  try {
    const { model, max_tokens, messages } = req.body;
    
    const response = await anthropic.messages.create({
      model: model || 'claude-sonnet-4-5-20250929',
      max_tokens: max_tokens || 1200,
      messages: messages
    });

    res.json(response);
  } catch (error) {
    console.error('Anthropic API error:', error);
    res.status(500).json({ error: error.message });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
