import React, { useState, useEffect } from 'react';
import { Container, Grid, Card, CardContent, Typography, Button, CircularProgress } from '@mui/material';
import { VideoCameraFront } from '@mui/icons-material';
import axios from 'axios';

const Dashboard = () => {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCameras = async () => {
      try {
        const response = await axios.get('http://localhost:5000/api/cameras');
        setCameras(response.data);
      } catch (error) {
        console.error('Error fetching cameras:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCameras();
  }, []);

  if (loading) {
    return (
      <Container>
        <CircularProgress />
      </Container>
    );
  }

  return (
    <Container>
      <Typography variant="h4" component="h1" gutterBottom>
        Blink Camera Dashboard
      </Typography>
      <Grid container spacing={3}>
        {cameras.map((camera) => (
          <Grid item xs={12} sm={6} md={4} key={camera.id}>
            <Card>
              <CardContent>
                <Typography variant="h6" component="h2">
                  {camera.name}
                </Typography>
                <Typography color="textSecondary" gutterBottom>
                  Status: {camera.status}
                </Typography>
                <Typography color="textSecondary">
                  Last Activity: {new Date(camera.lastActivity).toLocaleString()}
                </Typography>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<VideoCameraFront />}
                  href={`/camera/${camera.id}`}
                >
                  View Camera
                </Button>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default Dashboard;
