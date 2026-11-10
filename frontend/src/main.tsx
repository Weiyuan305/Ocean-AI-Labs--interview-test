import React from 'react';
import ReactDOM from 'react-dom/client';
import {ConfigProvider} from 'antd';
import enUS from 'antd/locale/en_US';
import App from './App';
import './style.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><ConfigProvider locale={enUS} theme={{token:{colorPrimary:'#176b70',borderRadius:6,fontFamily:'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'}}}><App/></ConfigProvider></React.StrictMode>);
