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

              {/* Device Status */}
              <Card data-testid="device-status-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-2xl">🔧</span>
                    Device Status
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {deviceStatus ? (
                    <>
                      <div className="flex items-center gap-2">
                        <Badge 
                          className={deviceStatus.connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}
                          data-testid="connection-status"
                        >
                          {deviceStatus.connected ? 'Connected' : 'Disconnected'}
                        </Badge>
                        {deviceStatus.mock_mode && (
                          <Badge className="bg-yellow-100 text-yellow-800" data-testid="mock-mode-badge">
                            Mock Mode
                          </Badge>
                        )}
                      </div>
                      
                      {deviceStatus.device_path && (
                        <p className="text-sm text-gray-600">
                          <strong>Device Path:</strong> {deviceStatus.device_path}
                        </p>
                      )}
                      
                      <div className="bg-gray-50 p-3 rounded text-sm font-mono">
                        <div className="max-h-32 overflow-y-auto">
                          {deviceStatus.output}
                        </div>
                      </div>

                      <Button
                        onClick={checkDeviceStatus}
                        variant="outline"
                        className="w-full"
                        data-testid="refresh-device-btn"
                      >
                        Refresh Status
                      </Button>
                    </>
                  ) : (
                    <div className="text-center py-4">
                      <p className="text-gray-500">Loading device status...</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Device Tab */}
          <TabsContent value="device">
            <Card>
              <CardHeader>
                <CardTitle>Proxmark3 Device Information</CardTitle>
              </CardHeader>
              <CardContent>
                {deviceStatus ? (
                  <div className="space-y-4">
                    <Alert>
                      <AlertDescription>
                        <strong>Connection Status:</strong> {deviceStatus.connected ? 'Connected' : 'Not Connected'}
                      </AlertDescription>
                    </Alert>
                    
                    {deviceStatus.device_path && (
                      <Alert>
                        <AlertDescription>
                          <strong>Device Path:</strong> {deviceStatus.device_path}
                        </AlertDescription>
                      </Alert>
                    )}
                    
                    <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm overflow-auto">
                      <pre>{deviceStatus.output}</pre>
                    </div>
                  </div>
                ) : (
                  <p>Loading device information...</p>
                )}
              </CardContent>
            </Card>
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

          {/* Config Tab */}
          <TabsContent value="config">
            <Card>
              <CardHeader>
                <CardTitle>Configuration Settings</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Alert>
                    <AlertDescription>
                      Configuration settings will be implemented in the next phase.
                      Current settings are loaded from /etc/filatag/config.json
                    </AlertDescription>
                  </Alert>
                </div>
              </CardContent>
            </Card>
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

          {/* Tag Programming Steps */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Tag 1 */}
            <Card className="relative" data-testid="tag1-card">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Tag #1</span>
                  <Badge className={`${getStatusColor(getTagStatus(1))} text-white`}>
                    {getTagStatus(1)?.toUpperCase() || 'PENDING'}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {getTagStatus(1) === 'pending' && (
                  <div className="space-y-3">
                    <Alert>
                      <AlertDescription>
                        Place the first RFID tag on the Proxmark3 antenna and click program.
                      </AlertDescription>
                    </Alert>
                    <Button
                      onClick={() => programTag(1)}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                      data-testid="program-tag1-btn"
                    >
                      Program Tag #1
                    </Button>
                  </div>
                )}
                
                {(['writing', 'verifying'].includes(getTagStatus(1))) && (
                  <div className="space-y-3">
                    <Alert>
                      <AlertDescription>
                        {getTagStatus(1) === 'writing' ? 'Writing data to tag...' : 'Verifying written data...'}
                      </AlertDescription>
                    </Alert>
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                      <span className="text-sm">Processing...</span>
                    </div>
                  </div>
                )}

                {(['pass', 'fail', 'error'].includes(getTagStatus(1))) && (
                  <Alert className={getTagStatus(1) === 'pass' ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}>
                    <AlertDescription>
                      {getTagStatus(1) === 'pass' && 'Tag #1 programmed successfully!'}
                      {getTagStatus(1) === 'fail' && 'Tag #1 programming failed. Please retry.'}
                      {getTagStatus(1) === 'error' && 'Error occurred during Tag #1 programming.'}
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
                  <Badge className={`${getStatusColor(getTagStatus(2))} text-white`}>
                    {getTagStatus(2)?.toUpperCase() || 'PENDING'}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {getTagStatus(2) === 'pending' && (
                  <div className="space-y-3">
                    <Alert>
                      <AlertDescription>
                        {getTagStatus(1) === 'pass' 
                          ? 'Remove Tag #1 and place the second RFID tag on the antenna.'
                          : 'Complete Tag #1 programming first.'
                        }
                      </AlertDescription>
                    </Alert>
                    <Button
                      onClick={() => programTag(2)}
                      disabled={getTagStatus(1) !== 'pass'}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white disabled:bg-gray-300"
                      data-testid="program-tag2-btn"
                    >
                      Program Tag #2
                    </Button>
                  </div>
                )}
                
                {(['writing', 'verifying'].includes(getTagStatus(2))) && (
                  <div className="space-y-3">
                    <Alert>
                      <AlertDescription>
                        {getTagStatus(2) === 'writing' ? 'Writing data to tag...' : 'Verifying written data...'}
                      </AlertDescription>
                    </Alert>
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                      <span className="text-sm">Processing...</span>
                    </div>
                  </div>
                )}

                {(['pass', 'fail', 'error'].includes(getTagStatus(2))) && (
                  <Alert className={getTagStatus(2) === 'pass' ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}>
                    <AlertDescription>
                      {getTagStatus(2) === 'pass' && 'Tag #2 programmed successfully!'}
                      {getTagStatus(2) === 'fail' && 'Tag #2 programming failed. Please retry.'}
                      {getTagStatus(2) === 'error' && 'Error occurred during Tag #2 programming.'}
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Session Complete */}
          {getTagStatus(1) === 'pass' && getTagStatus(2) === 'pass' && (
            <Alert className="border-green-200 bg-green-50">
              <AlertDescription className="text-center font-medium text-green-800">
                🎉 Both tags programmed successfully! Spool {sessionData.spool_id} is ready.
              </AlertDescription>
            </Alert>
          )}

          {/* Close Button */}
          <div className="flex justify-end space-x-2">
            <Button 
              variant="outline" 
              onClick={onClose}
              data-testid="close-programming-btn"
            >
              Close
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