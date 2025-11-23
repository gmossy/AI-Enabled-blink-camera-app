import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Typography, Box, CircularProgress } from '@mui/material';
import axios from 'axios';

const CameraView = () => {
  const { id } = useParams();
  const [camera, setCamera] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCamera = async () => {
      try {
        const response = await axios.get(`http://localhost:5000/api/cameras/${id}`);
        setCamera(response.data);
      } catch (error) {
        console.error('Error fetching camera:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCamera();
  }, [id]);

  if (loading) {
    return (
      <Container>
        <CircularProgress />
      </Container>
    );
  }

  if (!camera) {
    return (
      <Container>
        <Typography variant="h6">Camera not found</Typography>
      </Container>
    );
  }

  return (
    <Container>
      <Typography variant="h4" component="h1" gutterBottom>
        {camera.name}
      </Typography>
      <Box sx={{ mt: 2 }}>
        {/* TODO: Add video stream component here */}
        <Typography variant="body1">
          Status: {camera.status}
        </Typography>
        <Typography variant="body1">
          Last Activity: {new Date(camera.lastActivity).toLocaleString()}
        </Typography>
      </Box>
    </Container>
  );
};

export default CameraView;
