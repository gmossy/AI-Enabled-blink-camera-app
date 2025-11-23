const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const port = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

// Routes
app.get('/api/cameras', async (req, res) => {
  try {
    // TODO: Implement Blink camera API integration
    const cameras = [
      {
        id: 'front-door',
        name: 'Front Door',
        status: 'online',
        lastActivity: new Date().toISOString()
      },
      {
        id: 'back-yard',
        name: 'Back Yard',
        status: 'online',
        lastActivity: new Date().toISOString()
      }
    ];
    res.json(cameras);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
