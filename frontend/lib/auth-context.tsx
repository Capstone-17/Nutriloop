'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'patient' | 'supervisor';
  profile?: UserProfile;
}

export interface UserProfile {
  age: number;
  sex: 'male' | 'female';
  weight: number;
  height: number;
  activityLevel: string;
  selectedDiseases: string[];
  healthMetrics: {
    glucose: number;
    systolic: number;
    diastolic: number;
    creatinine?: number;
    urea?: number;
  };
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string, role: 'patient' | 'supervisor') => Promise<void>;
  signup: (email: string, password: string, name: string, role: 'patient' | 'supervisor', profile?: UserProfile) => Promise<void>;
  logout: () => void;
  updateProfile: (profile: UserProfile) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Mock user database
  const mockUsers: Record<string, { password: string; name: string; role: 'patient' | 'supervisor' }> = {
    'patient@nutriloop.com': { password: 'patient123', name: 'John Patient', role: 'patient' },
    'supervisor@nutriloop.com': { password: 'supervisor123', name: 'Dr. Sarah Supervisor', role: 'supervisor' },
  };

  // Initialize from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('nutriloop_user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch (e) {
        localStorage.removeItem('nutriloop_user');
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string, role: 'patient' | 'supervisor') => {
    setIsLoading(true);
    try {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 500));

      const storedUsers = JSON.parse(localStorage.getItem('nutriloop_users') || '{}');
      const mockUser = mockUsers[email] || storedUsers[email];
      if (!mockUser || mockUser.password !== password || mockUser.role !== role) {
        throw new Error('Invalid credentials or role mismatch');
      }

      const newUser: User = {
        id: Math.random().toString(36).substr(2, 9),
        email,
        name: mockUser.name,
        role,
        profile: JSON.parse(localStorage.getItem(`nutriloop_profile_${email}`) || 'null') || undefined,
      };

      setUser(newUser);
      localStorage.setItem('nutriloop_user', JSON.stringify(newUser));
    } finally {
      setIsLoading(false);
    }
  };

  const signup = async (email: string, password: string, name: string, role: 'patient' | 'supervisor', profile?: UserProfile) => {
    setIsLoading(true);
    try {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 500));

      const storedUsers = JSON.parse(localStorage.getItem('nutriloop_users') || '{}');
      if (mockUsers[email] || storedUsers[email]) {
        throw new Error('Email already registered');
      }

      const newUser: User = {
        id: Math.random().toString(36).substr(2, 9),
        email,
        name,
        role,
        profile,
      };

      // Store in mock database
      mockUsers[email] = { password, name, role };
      localStorage.setItem('nutriloop_users', JSON.stringify({
        ...storedUsers,
        [email]: { password, name, role },
      }));

      if (profile) {
        localStorage.setItem(`nutriloop_profile_${email}`, JSON.stringify(profile));
      }
      setUser(newUser);
      localStorage.setItem('nutriloop_user', JSON.stringify(newUser));
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('nutriloop_user');
  };

  const updateProfile = async (profile: UserProfile) => {
    if (!user) throw new Error('No user logged in');
    try {
      // Update in state
      const updatedUser = { ...user, profile };
      setUser(updatedUser);
      // Persist to localStorage
      localStorage.setItem('nutriloop_user', JSON.stringify(updatedUser));
      localStorage.setItem(`nutriloop_profile_${user.email}`, JSON.stringify(profile));
    } finally {
      // Empty
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, signup, logout, updateProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
