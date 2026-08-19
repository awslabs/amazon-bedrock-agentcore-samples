import React, { useState } from 'react';
import '../styles/travel-theme.css';

interface TravelLayoutProps {
  user: any;
  onSignOut: () => void;
  children?: React.ReactNode;
}

const TravelLayout: React.FC<TravelLayoutProps> = ({ user, onSignOut, children }) => {
  const [activeTab, setActiveTab] = useState('stays');

  return (
    <div>
      {/* Top Navigation */}
      <header className="travel-header">
        <div className="travel-nav-container">
          <div className="travel-logo">
            <img src="/VISA-Logo-2006.png" alt="Visa" style={{ height: '32px' }} />
            <span>Travel Concierge</span>
          </div>
          
          <nav className="travel-nav-links">
            <a href="#" className="travel-nav-link active">Stays</a>
            <a href="#" className="travel-nav-link">Flights</a>
            <a href="#" className="travel-nav-link">Cars</a>
            <a href="#" className="travel-nav-link">Packages</a>
            <a href="#" className="travel-nav-link">Things to do</a>
          </nav>
          
          <div className="travel-user-menu">
            <button className="travel-user-btn">
              {user.username}
            </button>
            <button className="travel-user-btn" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Hero Search Section */}
      <section className="travel-hero">
        <div className="travel-hero-container">
          <h1 className="travel-hero-title">Find your next adventure</h1>
          <p className="travel-hero-subtitle">Search hotels, flights, and more with AI assistance</p>
          
          <div className="travel-search-tabs">
            <button 
              className={`travel-search-tab ${activeTab === 'stays' ? 'active' : ''}`}
              onClick={() => setActiveTab('stays')}
            >
              Stays
            </button>
            <button 
              className={`travel-search-tab ${activeTab === 'flights' ? 'active' : ''}`}
              onClick={() => setActiveTab('flights')}
            >
              Flights
            </button>
            <button 
              className={`travel-search-tab ${activeTab === 'cars' ? 'active' : ''}`}
              onClick={() => setActiveTab('cars')}
            >
              Cars
            </button>
          </div>
          
          <div className="travel-search-box">
            <div className="travel-search-inputs">
              <div className="travel-input-group">
                <label className="travel-input-label">Going to</label>
                <input 
                  type="text" 
                  className="travel-input" 
                  placeholder="Where are you going?"
                />
              </div>
              
              <div className="travel-input-group">
                <label className="travel-input-label">Check-in</label>
                <input 
                  type="date" 
                  className="travel-input"
                />
              </div>
              
              <div className="travel-input-group">
                <label className="travel-input-label">Check-out</label>
                <input 
                  type="date" 
                  className="travel-input"
                />
              </div>
              
              <div className="travel-input-group">
                <label className="travel-input-label">Travelers</label>
                <select className="travel-input">
                  <option>1 room, 2 travelers</option>
                  <option>2 rooms, 4 travelers</option>
                </select>
              </div>
              
              <button className="travel-search-btn">
                Search
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      {children}
    </div>
  );
};

export default TravelLayout;
