import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Button } from './components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Badge } from './components/ui/badge';
import { Progress } from './components/ui/progress';
import { Alert, AlertDescription } from './components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import { toast } from 'sonner';
import { Toaster } from './components/ui/sonner';
import '@/App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Utility function for status colors
const getStatusColor = (status) => {
  switch (status) {
    case 'pass': return 'bg-green-500';
    case 'fail': return 'bg-red-500';
    case 'writing': return 'bg-blue-500 animate-pulse';
    case 'verifying': return 'bg-yellow-500 animate-pulse';
    case 'error': return 'bg-gray-500';
    default: return 'bg-gray-300';
  }
};

// Main Dashboard Component
const Dashboard = () => {
  const [filaments, setFilaments] = useState([]);
  const [deviceStatus, setDeviceStatus] = useState(null);
  const [selectedFilament, setSelectedFilament] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentSession, setCurrentSession] = useState(null);
  const [showProgramming, setShowProgramming] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [logs, setLogs] = useState([]);
  
  // Auto-detection states
  const [cameraStatus, setCameraStatus] = useState(null);
  const [autoDetectionMode, setAutoDetectionMode] = useState(true);
  const [barcodeScanResult, setBarcodeScanResult] = useState(null);
  const [autoSessionStatus, setAutoSessionStatus] = useState(null);
  const [cameraFrame, setCameraFrame] = useState(null);
  
  // Settings states
  const [settings, setSettings] = useState({
    camera_enabled: true,
    auto_rfid_detection: true,
    device_path: 'auto',
    verification_mode: 'strict',
    mock_mode: false,
    retry_count: 3,
    detection_interval: 1.0,
    barcode_scan_interval: 2.0,
    default_keys: ['FFFFFFFFFFFF', '000000000000']
  });
  const [settingsLoading, setSettingsLoading] = useState(false);

  useEffect(() => {
    loadFilaments();
    checkDeviceStatus();
    loadLogs();
    checkCameraStatus();
  }, []);

  // Auto-detection polling
  useEffect(() => {
    let interval;
    if (autoDetectionMode && currentSession) {
      interval = setInterval(() => {
        checkAutoSessionStatus();
        scanBarcode();
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [autoDetectionMode, currentSession]);

  const loadFilaments = async () => {
    try {
      const response = await axios.get(`${API}/filaments`);
      setFilaments(response.data);
    } catch (error) {
      toast.error('Failed to load filaments');
      console.error('Error loading filaments:', error);
    }
  };

  const checkDeviceStatus = async () => {
    try {
      const response = await axios.get(`${API}/device/status`);
      setDeviceStatus(response.data);
      if (!response.data.connected) {
        toast.warning('Proxmark3 device not connected');
      }
    } catch (error) {
      toast.error('Failed to check device status');
      console.error('Error checking device:', error);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await axios.get(`${API}/logs?limit=50`);
      setLogs(response.data);
    } catch (error) {
      console.error('Error loading logs:', error);
    }
  };

  const checkCameraStatus = async () => {
    try {
      const response = await axios.get(`${API}/camera/status`);
      setCameraStatus(response.data);
    } catch (error) {
      console.error('Error checking camera status:', error);
      setCameraStatus({ available: false, initialized: false, scanning: false });
    }
  };

  const scanBarcode = async () => {
    if (!cameraStatus?.initialized) return;
    
    try {
      const response = await axios.get(`${API}/barcode/scan`);
      if (response.data.barcode && response.data.sku) {
        setBarcodeScanResult(response.data);
        setSelectedFilament(response.data.sku);
        toast.success(`Barcode detected: ${response.data.sku}`);
      }
    } catch (error) {
      console.error('Error scanning barcode:', error);
    }
  };

  const checkAutoSessionStatus = async () => {
    if (!currentSession) return;
    
    try {
      const response = await axios.get(`${API}/auto-programming/status`);
      setAutoSessionStatus(response.data);
    } catch (error) {
      console.error('Error checking auto-session status:', error);
    }
  };

  const startProgramming = async () => {
    if (!selectedFilament) {
      toast.error('Please select a filament type');
      return;
    }

    setLoading(true);
    try {
      if (autoDetectionMode) {
        // Start auto-programming session
        const response = await axios.post(`${API}/auto-programming/start`, {
          sku: selectedFilament
        });
        
        setCurrentSession(response.data);
        setShowProgramming(true);
        toast.success('Auto-programming started - place Tag #1 on antenna');
      } else {
        // Legacy manual mode (if needed)
        const response = await axios.post(`${API}/programming/start`, {
          sku: selectedFilament,
          spool_id: `AUTO_${Date.now()}`,
          operator: 'AutoSystem'
        });
        
        setCurrentSession(response.data);
        setShowProgramming(true);
        toast.success('Programming session started');
      }
    } catch (error) {
      toast.error('Failed to start programming session');
      console.error('Error starting session:', error);
    } finally {
      setLoading(false);
    }
  };

  const stopProgramming = async () => {
    try {
      await axios.post(`${API}/auto-programming/stop`);
      setCurrentSession(null);
      setShowProgramming(false);
      setAutoSessionStatus(null);
      toast.info('Programming stopped');
    } catch (error) {
      console.error('Error stopping programming:', error);
    }
  };

  const filteredFilaments = filaments.filter(filament =>
    filament.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
    filament.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    filament.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-800 mb-2">
            Filatag RFID Programmer
          </h1>
          <p className="text-slate-600">
            Program MIFARE Classic RFID tags for filament spools using Proxmark3
          </p>
        </div>

        <Tabs defaultValue="programming" className="w-full">
          <TabsList className="grid w-full grid-cols-4 mb-8">
            <TabsTrigger value="programming" data-testid="programming-tab">Programming</TabsTrigger>
            <TabsTrigger value="device" data-testid="device-tab">Device Status</TabsTrigger>
            <TabsTrigger value="logs" data-testid="logs-tab">Logs</TabsTrigger>
            <TabsTrigger value="config" data-testid="config-tab">Settings</TabsTrigger>
          </TabsList>

          {/* Programming Tab */}
          <TabsContent value="programming">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Automated Workflow */}
              <Card data-testid="auto-workflow-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-2xl">🤖</span>
                    Automated Programming
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Barcode Scanning Section */}
                  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-lg">📷</span>
                      <span className="font-medium">Step 1: Scan Barcode</span>
                      {cameraStatus?.available && (
                        <Badge className={cameraStatus.initialized ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}>
                          {cameraStatus.initialized ? 'Camera Ready' : 'Camera Available'}
                        </Badge>
                      )}
                    </div>
                    
                    {cameraStatus?.available ? (
                      <div className="space-y-2">
                        {barcodeScanResult ? (
                          <Alert className="border-green-200 bg-green-50">
                            <AlertDescription>
                              ✅ Barcode detected: <strong>{barcodeScanResult.barcode}</strong>
                              {barcodeScanResult.sku && (
                                <span> → SKU: <strong>{barcodeScanResult.sku}</strong></span>
                              )}
                            </AlertDescription>
                          </Alert>
                        ) : (
                          <Alert>
                            <AlertDescription>
                              📷 Point camera at filament spool barcode for automatic detection
                            </AlertDescription>
                          </Alert>
                        )}
                      </div>
                    ) : (
                      <Alert className="border-yellow-200 bg-yellow-50">
                        <AlertDescription>
                          📷 Camera not available - manual filament selection required
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>

                  {/* Filament Selection */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">🏷️</span>
                      <span className="font-medium">Step 2: Confirm Filament Type</span>
                    </div>
                    
                    <div>
                      <Label htmlFor="search">Search Filaments</Label>
                      <Input
                        id="search"
                        placeholder="Search by SKU, name, or description..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        data-testid="filament-search-input"
                      />
                    </div>

                    <div>
                      <Select value={selectedFilament} onValueChange={setSelectedFilament}>
                        <SelectTrigger data-testid="filament-select">
                          <SelectValue placeholder="Choose filament..." />
                        </SelectTrigger>
                        <SelectContent>
                          {filteredFilaments.map((filament) => (
                            <SelectItem key={filament.sku} value={filament.sku}>
                              <div className="flex flex-col">
                                <span className="font-medium">{filament.sku} - {filament.name}</span>
                                <span className="text-sm text-gray-500">{filament.description}</span>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Programming Controls */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">⚡</span>
                      <span className="font-medium">Step 3: Start Auto-Programming</span>
                    </div>
                    
                    <Alert className="border-blue-200 bg-blue-50">
                      <AlertDescription>
                        <div className="space-y-1">
                          <div>✨ Automated workflow will:</div>
                          <div className="ml-4 text-sm space-y-1">
                            <div>• Detect when Tag #1 is placed on antenna</div>
                            <div>• Automatically program and verify Tag #1</div>
                            <div>• Prompt for Tag #2 placement</div>
                            <div>• Automatically program and verify Tag #2</div>
                            <div>• Complete when both tags are done</div>
                          </div>
                        </div>
                      </AlertDescription>
                    </Alert>

                    <Button
                      onClick={startProgramming}
                      disabled={loading || !selectedFilament}
                      className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-medium py-4 rounded-lg transition-all duration-200 transform hover:scale-[1.02]"
                      data-testid="start-auto-programming-btn"
                    >
                      {loading ? 'Starting Auto-Programming...' : '🚀 Start Auto-Programming'}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Simplified Device Status */}
              <Card data-testid="device-status-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-2xl">📟</span>
                    System Status
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Proxmark3</span>
                    <Badge 
                      className={deviceStatus?.connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}
                      data-testid="proxmark-status"
                    >
                      {deviceStatus?.connected ? 'Ready' : 'Offline'}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Camera</span>
                    <Badge 
                      className={cameraStatus?.initialized ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}
                      data-testid="camera-status"
                    >
                      {cameraStatus?.initialized ? 'Ready' : 'Not Available'}
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Mode</span>
                    <Badge 
                      className={deviceStatus?.mock_mode ? 'bg-yellow-100 text-yellow-800' : 'bg-blue-100 text-blue-800'}
                      data-testid="mode-status"
                    >
                      {deviceStatus?.mock_mode ? 'Mock' : 'Live'}
                    </Badge>
                  </div>

                  {(!deviceStatus?.connected || !cameraStatus?.initialized) && (
                    <Alert className="mt-3">
                      <AlertDescription className="text-xs">
                        Check Device Status tab for detailed information
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Device Tab */}
          <TabsContent value="device">
            <div className="space-y-6">
              {/* Proxmark3 Device */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-xl">📡</span>
                    Proxmark3 RFID Device
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {deviceStatus ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-sm font-medium">Status</Label>
                          <div className="flex items-center gap-2 mt-1">
                            <div className={`w-3 h-3 rounded-full ${deviceStatus.connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                            <span className="text-sm">{deviceStatus.connected ? 'Connected' : 'Disconnected'}</span>
                          </div>
                        </div>
                        <div>
                          <Label className="text-sm font-medium">Mode</Label>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge className={deviceStatus.mock_mode ? 'bg-yellow-100 text-yellow-800' : 'bg-blue-100 text-blue-800'}>
                              {deviceStatus.mock_mode ? 'Mock Mode' : 'Hardware Mode'}
                            </Badge>
                          </div>
                        </div>
                      </div>
                      
                      {deviceStatus.device_path && (
                        <div>
                          <Label className="text-sm font-medium">Device Path</Label>
                          <p className="text-sm text-gray-600 mt-1 font-mono">{deviceStatus.device_path}</p>
                        </div>
                      )}
                      
                      <div>
                        <Label className="text-sm font-medium">Device Output</Label>
                        <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm overflow-auto mt-2 max-h-40">
                          <pre>{deviceStatus.output}</pre>
                        </div>
                      </div>

                      <Button
                        onClick={checkDeviceStatus}
                        variant="outline"
                        className="w-full"
                        data-testid="refresh-proxmark-btn"
                      >
                        🔄 Refresh Proxmark3 Status
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-4">
                      <p className="text-gray-500">Loading device information...</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Camera Device */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-xl">📷</span>
                    USB Camera Device
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {cameraStatus ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <Label className="text-sm font-medium">Available</Label>
                          <div className="flex items-center gap-2 mt-1">
                            <div className={`w-3 h-3 rounded-full ${cameraStatus.available ? 'bg-green-500' : 'bg-red-500'}`}></div>
                            <span className="text-sm">{cameraStatus.available ? 'Yes' : 'No'}</span>
                          </div>
                        </div>
                        <div>
                          <Label className="text-sm font-medium">Initialized</Label>
                          <div className="flex items-center gap-2 mt-1">
                            <div className={`w-3 h-3 rounded-full ${cameraStatus.initialized ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                            <span className="text-sm">{cameraStatus.initialized ? 'Yes' : 'No'}</span>
                          </div>
                        </div>
                        <div>
                          <Label className="text-sm font-medium">Scanning</Label>
                          <div className="flex items-center gap-2 mt-1">
                            <div className={`w-3 h-3 rounded-full ${cameraStatus.scanning ? 'bg-blue-500 animate-pulse' : 'bg-gray-400'}`}></div>
                            <span className="text-sm">{cameraStatus.scanning ? 'Active' : 'Idle'}</span>
                          </div>
                        </div>
                      </div>

                      {!cameraStatus.available && (
                        <Alert className="border-yellow-200 bg-yellow-50">
                          <AlertDescription>
                            📷 No USB camera detected. Connect a USB webcam to enable barcode scanning.
                          </AlertDescription>
                        </Alert>
                      )}

                      {cameraStatus.available && !cameraStatus.initialized && (
                        <Alert className="border-blue-200 bg-blue-50">
                          <AlertDescription>
                            🔧 Camera available but not initialized. Enable in Settings to use barcode scanning.
                          </AlertDescription>
                        </Alert>
                      )}

                      <Button
                        onClick={checkCameraStatus}
                        variant="outline"
                        className="w-full"
                        data-testid="refresh-camera-btn"
                      >
                        🔄 Refresh Camera Status
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-4">
                      <p className="text-gray-500">Loading camera information...</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Logs Tab */}
          <TabsContent value="logs">
            <Card>
              <CardHeader>
                <CardTitle>Recent Activity Logs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {logs.length > 0 ? (
                    logs.map((log, index) => (
                      <div key={index} className="border-l-4 border-blue-400 pl-4 py-2 bg-slate-50 rounded">
                        <div className="flex justify-between items-start">
                          <span className="font-medium">{log.action}</span>
                          <span className="text-sm text-gray-500">
                            {new Date(log.timestamp).toLocaleString()}
                          </span>
                        </div>
                        {log.sku && <p className="text-sm">SKU: {log.sku}</p>}
                        {log.spool_id && <p className="text-sm">Spool: {log.spool_id}</p>}
                        {log.error && <p className="text-sm text-red-600">Error: {log.error}</p>}
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500 text-center py-4">No logs available</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="config">
            <SettingsPanel />
          </TabsContent>
        </Tabs>
      </div>

      {/* Programming Modal */}
      <ProgrammingModal
        session={currentSession}
        open={showProgramming}
        onClose={() => setShowProgramming(false)}
      />

      <Toaster />
    </div>
  );
};

// Auto-Programming Modal Component  
const ProgrammingModal = ({ session, open, onClose }) => {
  const [autoStatus, setAutoStatus] = useState(null);
  const [currentStep, setCurrentStep] = useState(1);

  useEffect(() => {
    if (!open || !session) return;

    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/auto-programming/status`);
        setAutoStatus(response.data);
        
        // Update current step based on auto-detection state
        if (response.data.current_tag_number) {
          setCurrentStep(response.data.current_tag_number);
        }
      } catch (error) {
        console.error('Error fetching auto-programming status:', error);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [open, session]);

  const stopAutoProgram = async () => {
    try {
      await axios.post(`${API}/auto-programming/stop`);
      onClose();
      toast.info('Auto-programming stopped');
    } catch (error) {
      console.error('Error stopping auto-programming:', error);
    }
  };

  const getAutoStateDisplay = (state) => {
    const stateMap = {
      'idle': { text: 'Ready', color: 'bg-gray-400' },
      'scanning': { text: 'Waiting for Tag', color: 'bg-blue-500 animate-pulse' },
      'tag_detected': { text: 'Tag Detected', color: 'bg-yellow-500' },
      'programming': { text: 'Programming', color: 'bg-blue-600 animate-pulse' },
      'verifying': { text: 'Verifying', color: 'bg-purple-500 animate-pulse' },
      'complete': { text: 'Complete', color: 'bg-green-500' },
      'error': { text: 'Error', color: 'bg-red-500' }
    };
    return stateMap[state] || stateMap['idle'];
  };

  const getProgressValue = () => {
    if (!autoStatus) return 0;
    
    if (autoStatus.state === 'complete') return 100;
    if (autoStatus.current_tag_number === 2) return 75;
    if (autoStatus.state === 'programming' || autoStatus.state === 'verifying') return 50;
    if (autoStatus.state === 'tag_detected') return 25;
    return 10;
  };

  if (!session) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl" data-testid="programming-modal">
        <DialogHeader>
          <DialogTitle className="text-2xl">🤖 Auto-Programming RFID Tags</DialogTitle>
          <p className="text-gray-600">
            SKU: {session.sku} | Mode: Automated Detection
          </p>
        </DialogHeader>
        
        <div className="space-y-6">
          {/* Overall Progress */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Overall Progress</span>
              <span>{Math.round(getProgressValue())}%</span>
            </div>
            <Progress value={getProgressValue()} className="h-2" />
          </div>

          {/* Auto-Detection Status */}
          <div className="space-y-4">
            <div className="text-center space-y-2">
              <div className="text-lg font-medium">
                Current Status: {autoStatus ? getAutoStateDisplay(autoStatus.state).text : 'Initializing...'}
              </div>
              <div className="text-sm text-gray-600">
                Programming Tag #{currentStep} of 2
              </div>
            </div>
          </div>

          {/* Tag Programming Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Tag 1 */}
            <Card className="relative" data-testid="tag1-card">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Tag #1</span>
                  <Badge className={`${autoStatus && currentStep >= 1 ? getAutoStateDisplay(autoStatus.state).color : 'bg-gray-300'} text-white`}>
                    {autoStatus && currentStep === 1 ? getAutoStateDisplay(autoStatus.state).text : 
                     (currentStep > 1 ? 'COMPLETE' : 'WAITING')}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {currentStep === 1 && autoStatus?.state === 'scanning' && (
                  <Alert className="border-blue-200 bg-blue-50">
                    <AlertDescription>
                      📡 Waiting for Tag #1 to be placed on Proxmark3 antenna...
                      <div className="mt-2 flex items-center space-x-2">
                        <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-sm">Auto-detecting...</span>
                      </div>
                    </AlertDescription>
                  </Alert>
                )}

                {currentStep === 1 && ['programming', 'verifying'].includes(autoStatus?.state) && (
                  <Alert className="border-purple-200 bg-purple-50">
                    <AlertDescription>
                      ⚡ {autoStatus.state === 'programming' ? 'Programming Tag #1...' : 'Verifying Tag #1...'}
                      <div className="mt-2 flex items-center space-x-2">
                        <div className="w-4 h-4 border-2 border-purple-600 border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-sm">Processing automatically...</span>
                      </div>
                    </AlertDescription>
                  </Alert>
                )}

                {currentStep > 1 && (
                  <Alert className="border-green-200 bg-green-50">
                    <AlertDescription>
                      ✅ Tag #1 programmed and verified successfully!
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* Tag 2 */}
            <Card className="relative" data-testid="tag2-card">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Tag #2</span>
                  <Badge className={`${autoStatus && currentStep === 2 ? getAutoStateDisplay(autoStatus.state).color : 
                    (autoStatus?.state === 'complete' ? 'bg-green-500' : 'bg-gray-300')} text-white`}>
                    {autoStatus?.state === 'complete' ? 'COMPLETE' :
                     (autoStatus && currentStep === 2 ? getAutoStateDisplay(autoStatus.state).text : 'WAITING')}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {currentStep < 2 && (
                  <Alert>
                    <AlertDescription>
                      ⏳ Waiting for Tag #1 to complete...
                    </AlertDescription>
                  </Alert>
                )}

                {currentStep === 2 && autoStatus?.state === 'scanning' && (
                  <Alert className="border-blue-200 bg-blue-50">
                    <AlertDescription>
                      📡 Remove Tag #1 and place Tag #2 on Proxmark3 antenna...
                      <div className="mt-2 flex items-center space-x-2">
                        <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-sm">Auto-detecting...</span>
                      </div>
                    </AlertDescription>
                  </Alert>
                )}

                {currentStep === 2 && ['programming', 'verifying'].includes(autoStatus?.state) && (
                  <Alert className="border-purple-200 bg-purple-50">
                    <AlertDescription>
                      ⚡ {autoStatus.state === 'programming' ? 'Programming Tag #2...' : 'Verifying Tag #2...'}
                      <div className="mt-2 flex items-center space-x-2">
                        <div className="w-4 h-4 border-2 border-purple-600 border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-sm">Processing automatically...</span>
                      </div>
                    </AlertDescription>
                  </Alert>
                )}

                {autoStatus?.state === 'complete' && (
                  <Alert className="border-green-200 bg-green-50">
                    <AlertDescription>
                      ✅ Tag #2 programmed and verified successfully!
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Session Complete */}
          {autoStatus?.state === 'complete' && (
            <Alert className="border-green-200 bg-green-50">
              <AlertDescription className="text-center font-medium text-green-800">
                🎉 Both tags programmed successfully! Auto-programming complete.
              </AlertDescription>
            </Alert>
          )}

          {/* Error State */}
          {autoStatus?.state === 'error' && (
            <Alert className="border-red-200 bg-red-50">
              <AlertDescription className="text-center font-medium text-red-800">
                ❌ Error occurred during auto-programming. Please try again.
              </AlertDescription>
            </Alert>
          )}

          {/* Control Buttons */}
          <div className="flex justify-between space-x-2">
            <Button 
              variant="outline" 
              onClick={stopAutoProgram}
              className="bg-red-50 text-red-600 hover:bg-red-100"
              data-testid="stop-programming-btn"
            >
              Stop Auto-Programming
            </Button>
            <Button 
              variant="outline" 
              onClick={onClose}
              data-testid="close-programming-btn"
            >
              {autoStatus?.state === 'complete' ? 'Close' : 'Minimize'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Main App Component
function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;