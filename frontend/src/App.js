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
import { Switch } from './components/ui/switch';
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

// SettingsPanel component is defined inside the Dashboard component below


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
    camera_device_path: '/dev/video0',
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
    loadSettings();
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
      if (response.data && response.data.logs) {
        setLogs(response.data.logs);
      } else if (Array.isArray(response.data)) {
        setLogs(response.data);
      } else {
        setLogs([]);
      }
    } catch (error) {
      console.error('Error loading logs:', error);
      setLogs([]);
    }
  };

  const clearLogs = async () => {
    try {
      await axios.post(`${API}/logs/clear`);
      setLogs([]);
      toast.success('Logs cleared successfully');
    } catch (error) {
      console.error('Error clearing logs:', error);
      toast.error('Failed to clear logs');
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

  const loadSettings = async () => {
    try {
      const response = await axios.get(`${API}/config`);
      setSettings({
        camera_enabled: response.data.camera_enabled ?? true,
        auto_rfid_detection: response.data.auto_rfid_detection ?? true,
        device_path: response.data.device_path || 'auto',
        camera_device_path: response.data.camera_device_path || '/dev/video0',
        verification_mode: response.data.strict_verification ? 'strict' : 'tolerant',
        mock_mode: response.data.mock_mode ?? false,
        retry_count: response.data.retries ?? 3,
        detection_interval: response.data.detection_interval ?? 1.0,
        barcode_scan_interval: response.data.barcode_scan_interval ?? 2.0,
        default_keys: response.data.default_keys || ['FFFFFFFFFFFF', '000000000000']
      });
    } catch (error) {
      console.error('Error loading settings:', error);
      toast.error('Failed to load settings');
    }
  };

  const saveSettings = async (newSettings) => {
    setSettingsLoading(true);
    try {
      const configData = {
        camera_enabled: newSettings.camera_enabled,
        auto_rfid_detection: newSettings.auto_rfid_detection,
        device_path: newSettings.device_path === 'auto' ? '/dev/ttyACM0' : newSettings.device_path,
        camera_device_path: newSettings.camera_device_path,
        strict_verification: newSettings.verification_mode === 'strict',
        mock_mode: newSettings.mock_mode,
        retries: newSettings.retry_count,
        detection_interval: newSettings.detection_interval,
        barcode_scan_interval: newSettings.barcode_scan_interval,
        default_keys: newSettings.default_keys
      };

      await axios.post(`${API}/config`, configData);
      setSettings(newSettings);
      toast.success('Settings saved successfully');
      
      // Refresh device status after settings change
      checkDeviceStatus();
      checkCameraStatus();
    } catch (error) {
      console.error('Error saving settings:', error);
      toast.error('Failed to save settings');
    } finally {
      setSettingsLoading(false);
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

  // Settings Panel Component
  const SettingsPanel = () => {
    // Settings panel states
    const [localSettings, setLocalSettings] = useState(settings);
    const [hasChanges, setHasChanges] = useState(false);

    useEffect(() => {
      setLocalSettings(settings);
    }, [settings]);

    const handleSettingChange = (key, value) => {
      const newSettings = { ...localSettings, [key]: value };
      setLocalSettings(newSettings);
      setHasChanges(JSON.stringify(newSettings) !== JSON.stringify(settings));
    };

    const handleSave = () => {
      saveSettings(localSettings);
      setHasChanges(false);
    };

    const handleReset = () => {
      setLocalSettings(settings);
      setHasChanges(false);
    };

    return (
      <div className="space-y-6">
        {/* Device Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-xl">🔧</span>
              Device Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Proxmark3 Settings */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium">Proxmark3 Configuration</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="device-path">Device Path</Label>
                  <Select 
                    value={localSettings.device_path} 
                    onValueChange={(value) => handleSettingChange('device_path', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">🔍 Auto-detect</SelectItem>
                      <SelectItem value="/dev/ttyACM0">/dev/ttyACM0</SelectItem>
                      <SelectItem value="/dev/ttyACM1">/dev/ttyACM1</SelectItem>
                      <SelectItem value="/dev/ttyUSB0">/dev/ttyUSB0</SelectItem>
                      <SelectItem value="/dev/ttyUSB1">/dev/ttyUSB1</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="verification-mode">Verification Mode</Label>
                  <Select 
                    value={localSettings.verification_mode} 
                    onValueChange={(value) => handleSettingChange('verification_mode', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="strict">🔒 Strict (Read-back verification)</SelectItem>
                      <SelectItem value="tolerant">⚡ Tolerant (Skip verification)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="retry-count">Retry Count</Label>
                  <Input
                    id="retry-count"
                    type="number"
                    min="1"
                    max="10"
                    value={localSettings.retry_count}
                    onChange={(e) => handleSettingChange('retry_count', parseInt(e.target.value))}
                  />
                </div>

                <div>
                  <Label htmlFor="detection-interval">Detection Interval (seconds)</Label>
                  <Input
                    id="detection-interval"
                    type="number"
                    min="0.5"
                    max="10"
                    step="0.5"
                    value={localSettings.detection_interval}
                    onChange={(e) => handleSettingChange('detection_interval', parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>

            {/* Camera Settings */}
            <div className="space-y-4 border-t pt-4">
              <h3 className="text-lg font-medium">Camera Configuration</h3>
              
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div>
                  <h4 className="font-medium">Camera System</h4>
                  <p className="text-sm text-gray-600">Enable USB webcam for barcode scanning</p>
                </div>
                <Switch 
                  checked={localSettings.camera_enabled}
                  onCheckedChange={(checked) => handleSettingChange('camera_enabled', checked)}
                />
              </div>

              {localSettings.camera_enabled && (
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="camera-device-path">Camera Device Path</Label>
                    <Select 
                      value={localSettings.camera_device_path} 
                      onValueChange={(value) => handleSettingChange('camera_device_path', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="/dev/video0">/dev/video0 (USB Camera 1)</SelectItem>
                        <SelectItem value="/dev/video1">/dev/video1 (USB Camera 2)</SelectItem>
                        <SelectItem value="/dev/video2">/dev/video2 (USB Camera 3)</SelectItem>
                        <SelectItem value="0">Camera Index 0</SelectItem>
                        <SelectItem value="1">Camera Index 1</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="barcode-scan-interval">Barcode Scan Interval (seconds)</Label>
                    <Input
                      id="barcode-scan-interval"
                      type="number"
                      min="0.5"
                      max="10"
                      step="0.5"
                      value={localSettings.barcode_scan_interval}
                      onChange={(e) => handleSettingChange('barcode_scan_interval', parseFloat(e.target.value))}
                    />
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Automation Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-xl">🤖</span>
              Automation Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <h4 className="font-medium">Auto RFID Detection</h4>
                <p className="text-sm text-gray-600">Automatically detect and program RFID tags when placed on antenna</p>
              </div>
              <Switch 
                checked={localSettings.auto_rfid_detection}
                onCheckedChange={(checked) => handleSettingChange('auto_rfid_detection', checked)}
              />
            </div>

            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <h4 className="font-medium">Mock Mode</h4>
                <p className="text-sm text-gray-600">Simulate hardware operations for testing and development</p>
              </div>
              <Switch 
                checked={localSettings.mock_mode}
                onCheckedChange={(checked) => handleSettingChange('mock_mode', checked)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Security Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-xl">🔐</span>
              Security Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Default MIFARE Keys</Label>
              <p className="text-sm text-gray-600 mb-2">Default keys used for MIFARE Classic authentication</p>
              <div className="space-y-2">
                {localSettings.default_keys.map((key, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <Input
                      value={key}
                      onChange={(e) => {
                        const newKeys = [...localSettings.default_keys];
                        newKeys[index] = e.target.value.toUpperCase();
                        handleSettingChange('default_keys', newKeys);
                      }}
                      placeholder="Enter 12-character hex key"
                      className="font-mono"
                      maxLength={12}
                    />
                    {localSettings.default_keys.length > 1 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const newKeys = localSettings.default_keys.filter((_, i) => i !== index);
                          handleSettingChange('default_keys', newKeys);
                        }}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const newKeys = [...localSettings.default_keys, 'FFFFFFFFFFFF'];
                    handleSettingChange('default_keys', newKeys);
                  }}
                >
                  Add Key
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Save/Reset Buttons */}
        <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-2">
            {hasChanges && (
              <Badge className="bg-yellow-100 text-yellow-800">Unsaved Changes</Badge>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={!hasChanges || settingsLoading}
            >
              Reset
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasChanges || settingsLoading}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {settingsLoading ? 'Saving...' : 'Save Settings'}
            </Button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="container mx-auto px-3 py-3 max-w-none min-h-screen flex flex-col">
        {/* Compact Touchscreen Header */}
        <div className="mb-4">
          <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-xl p-4 shadow-lg border border-slate-700">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="bg-white/10 backdrop-blur-sm rounded-lg p-2 border border-white/20">
                  <img 
                    src="/filaform-logo.png" 
                    alt="Filaform" 
                    className="h-6 w-auto drop-shadow-sm"
                  />
                </div>
                <div>
                  <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                    FilaTag PRO
                  </h1>
                  <p className="text-slate-300 text-xs font-medium tracking-wide">
                    RFID Programming System
                  </p>
                </div>
              </div>
              
              {/* Compact Status */}
              <div className="flex items-center gap-2 px-3 py-1 bg-green-500/20 rounded-full border border-green-400/30">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-green-400 text-xs font-medium">System Ready</span>
              </div>
            </div>
          </div>
        </div>

        <Tabs defaultValue="programming" className="w-full flex-1 flex flex-col overflow-hidden">
          <TabsList className="grid w-full grid-cols-4 mb-4 h-12 bg-white/80 backdrop-blur-sm border border-slate-200 rounded-lg shadow-sm">
            <TabsTrigger 
              value="programming" 
              data-testid="programming-tab"
              className="flex flex-col items-center gap-1 text-xs font-medium data-[state=active]:bg-slate-800 data-[state=active]:text-white min-h-[44px] transition-all"
            >
              <span className="text-base">🚀</span>
              Program
            </TabsTrigger>
            <TabsTrigger 
              value="device" 
              data-testid="device-tab"
              className="flex flex-col items-center gap-1 text-xs font-medium data-[state=active]:bg-slate-800 data-[state=active]:text-white min-h-[44px] transition-all"
            >
              <span className="text-base">📡</span>
              Status
            </TabsTrigger>
            <TabsTrigger 
              value="logs" 
              data-testid="logs-tab"
              className="flex flex-col items-center gap-1 text-xs font-medium data-[state=active]:bg-slate-800 data-[state=active]:text-white min-h-[44px] transition-all"
            >
              <span className="text-base">📊</span>
              Logs
            </TabsTrigger>
            <TabsTrigger 
              value="config" 
              data-testid="config-tab"
              className="flex flex-col items-center gap-1 text-xs font-medium data-[state=active]:bg-slate-800 data-[state=active]:text-white min-h-[44px] transition-all"
            >
              <span className="text-base">⚙️</span>
              Settings
            </TabsTrigger>
          </TabsList>

          {/* Scrollable content area */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden">
            {/* Programming Tab */}
            <TabsContent value="programming" className="h-full">
            <div className="grid grid-cols-1 gap-4">
              {/* Compact Automated Workflow */}
              <Card data-testid="auto-workflow-card" className="shadow-lg">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <span className="text-xl">🤖</span>
                    Auto Programming
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Compact Barcode Scanning */}
                  <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">📷</span>
                      <div>
                        <span className="font-medium text-sm">Barcode Scanner</span>
                        {barcodeScanResult ? (
                          <p className="text-xs text-green-600">✅ {barcodeScanResult.sku}</p>
                        ) : (
                          <p className="text-xs text-gray-600">Ready to scan</p>
                        )}
                      </div>
                    </div>
                    <Badge className={cameraStatus?.initialized ? 'bg-green-500 text-white' : 'bg-gray-400 text-white'}>
                      {cameraStatus?.initialized ? 'Ready' : 'Off'}
                    </Badge>
                  </div>

                  {/* Compact Filament Selection */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🏷️</span>
                      <span className="font-medium text-sm">Filament Type</span>
                    </div>
                    
                    <Input
                      placeholder="Search filaments..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      data-testid="filament-search-input"
                      className="h-10 text-base"
                    />

                    <Select value={selectedFilament} onValueChange={setSelectedFilament}>
                      <SelectTrigger data-testid="filament-select" className="h-12 text-base">
                        <SelectValue placeholder="Select filament type" />
                      </SelectTrigger>
                      <SelectContent>
                        {filteredFilaments.map((filament) => (
                          <SelectItem key={filament.sku} value={filament.sku} className="h-12">
                            <div>
                              <div className="font-medium">{filament.sku} - {filament.name}</div>
                              <div className="text-xs text-gray-500">{filament.description}</div>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
                      className="w-full bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-700 hover:to-emerald-800 text-white font-bold py-6 text-lg rounded-xl shadow-lg min-h-[60px] border border-emerald-500/30"
                      data-testid="start-auto-programming-btn"
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                          Starting...
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          <span className="text-xl">🚀</span>
                          START PROGRAMMING
                        </span>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Compact System Status */}
              <Card data-testid="device-status-card" className="shadow-lg">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <span className="text-lg">⚡</span>
                    System Status
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Compact Status Grid */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="flex flex-col items-center p-2 bg-slate-50 rounded-lg">
                      <span className="text-lg mb-1">📡</span>
                      <span className="text-xs font-medium">Proxmark3</span>
                      <Badge 
                        className={`${deviceStatus?.connected ? 'bg-green-500' : 'bg-red-500'} text-white text-xs px-2 py-0 mt-1`}
                        data-testid="proxmark-status"
                      >
                        {deviceStatus?.connected ? 'Ready' : 'Off'}
                      </Badge>
                    </div>

                    <div className="flex flex-col items-center p-2 bg-slate-50 rounded-lg">
                      <span className="text-lg mb-1">📷</span>
                      <span className="text-xs font-medium">Camera</span>
                      <Badge 
                        className={`${cameraStatus?.initialized ? 'bg-green-500' : 'bg-gray-500'} text-white text-xs px-2 py-0 mt-1`}
                        data-testid="camera-status"
                      >
                        {cameraStatus?.initialized ? 'Ready' : 'Off'}
                      </Badge>
                    </div>

                    <div className="flex flex-col items-center p-2 bg-slate-50 rounded-lg">
                      <span className="text-lg mb-1">⚙️</span>
                      <span className="text-xs font-medium">Mode</span>
                      <Badge 
                        className={`${deviceStatus?.mock_mode ? 'bg-orange-500' : 'bg-blue-500'} text-white text-xs px-2 py-0 mt-1`}
                        data-testid="mode-status"
                      >
                        {deviceStatus?.mock_mode ? 'Mock' : 'Live'}
                      </Badge>
                    </div>
                  </div>
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
                <div className="flex justify-between items-center">
                  <CardTitle>Recent Activity Logs</CardTitle>
                  <div className="flex gap-2">
                    <Button
                      onClick={loadLogs}
                      variant="outline"
                      className="min-h-[44px] px-4"
                      data-testid="refresh-logs-btn"
                    >
                      🔄 Refresh
                    </Button>
                    <Button
                      onClick={clearLogs}
                      variant="outline" 
                      className="text-red-600 hover:text-red-700 hover:bg-red-50 min-h-[44px] px-4"
                      data-testid="clear-logs-btn"
                    >
                      🗑️ Clear
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {logs.length > 0 ? (
                    logs.map((log, index) => (
                      <div key={index} className="border-l-4 border-blue-400 pl-4 py-2 bg-slate-50 rounded">
                        <div className="flex justify-between items-start">
                          <span className="font-medium capitalize">{log.action.replace(/_/g, ' ')}</span>
                          <span className="text-sm text-gray-500">
                            {new Date(log.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <div className="text-sm text-gray-600 mt-1">
                          {log.session_id && <span className="mr-4">Session: {log.session_id.slice(-8)}</span>}
                          {log.sku && <span className="mr-4">SKU: {log.sku}</span>}
                          {log.spool_id && <span className="mr-4">Spool: {log.spool_id}</span>}
                          {log.tag_number && <span className="mr-4">Tag: #{log.tag_number}</span>}
                        </div>
                        {log.error && (
                          <p className="text-sm text-red-600 mt-1 bg-red-50 p-2 rounded">
                            Error: {log.error}
                          </p>
                        )}
                        {log.hash && (
                          <p className="text-xs text-gray-400 font-mono mt-1">
                            Hash: {log.hash.slice(0, 16)}...
                          </p>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-gray-500 mb-2">No logs available</p>
                      <Button
                        onClick={loadLogs}
                        variant="outline"
                        size="sm"
                      >
                        🔄 Refresh Logs
                      </Button>
                    </div>
                  )}
                </div>
                {logs.length > 0 && (
                  <div className="mt-4 text-sm text-gray-500 text-center">
                    Showing {logs.length} most recent entries
                  </div>
                )}
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
      <DialogContent className="max-w-4xl w-[95vw] max-h-[90vh] overflow-y-auto" data-testid="programming-modal">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Auto-Programming Session
          </DialogTitle>
          <div className="flex items-center gap-4 text-sm">
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full font-medium">
              SKU: {session.sku}
            </span>
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full font-medium">
              Automated Detection
            </span>
          </div>
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

          {/* Touch-Optimized Tag Programming */}
          <div className="grid grid-cols-2 gap-3">
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