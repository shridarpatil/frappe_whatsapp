// index.js
const express = require('express');
const app = express();

app.get('/', (req, res) => {
  res.send('HedstApp başarıyla çalışıyor 🎉');
});

const PORT = 8080;
app.listen(PORT, () => {
  console.log(`Sunucu ${PORT} portunda çalışıyor`);
});
