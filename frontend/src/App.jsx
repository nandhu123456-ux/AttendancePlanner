import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Settings from "./pages/Settings";
import Subjects from "./pages/Subjects";
import Prediction from "./pages/Prediction";
import Login from "./pages/Login";

function ProtectedRoute({ children }) {
  return localStorage.getItem("token") ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return <BrowserRouter><Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
    <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
    <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
    <Route path="/subjects" element={<ProtectedRoute><Subjects /></ProtectedRoute>} />
    <Route path="/prediction" element={<ProtectedRoute><Prediction /></ProtectedRoute>} />
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes></BrowserRouter>;
}
