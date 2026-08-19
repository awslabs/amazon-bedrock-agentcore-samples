import React from 'react';

interface DynamicMapProps {
  destination: string;
  latitude?: number;
  longitude?: number;
  attractions?: Array<{
    id: string;
    name: string;
    price?: string;
    duration?: string;
    rating?: number;
    description: string;
  }>;
}

const DynamicMap: React.FC<DynamicMapProps> = ({ 
  destination, 
  latitude, 
  longitude, 
  attractions = [] 
}) => {
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
  const mapUrl = latitude && longitude
    ? `https://www.google.com/maps/embed/v1/place?key=${apiKey}&q=${latitude},${longitude}&zoom=13`
    : `https://www.google.com/maps/embed/v1/place?key=${apiKey}&q=${encodeURIComponent(destination)}`;

  return (
    <div className="bg-white rounded-md shadow-sm mb-6 overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-800">Attractions Map</h3>
        <p className="text-sm text-gray-600">Explore attractions in {destination}</p>
      </div>
      
      <div className="h-80 w-full">
        <iframe 
          title={`${destination} Attractions Map`}
          src={mapUrl}
          width="100%" 
          height="100%" 
          style={{ border: 0 }} 
          allowFullScreen
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>
      
      {attractions.length > 0 && (
        <div className="p-4 bg-blue-50">
          <h4 className="font-medium text-gray-800 mb-2">Recommended Activities</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {attractions.map(attraction => (
              <div 
                key={attraction.id} 
                className="border rounded bg-white p-3 cursor-pointer hover:border-blue-500 hover:shadow-md transition-all"
              >
                <div className="font-medium text-gray-800">{attraction.name}</div>
                {(attraction.price || attraction.duration || attraction.rating) && (
                  <div className="text-sm text-gray-600">
                    {attraction.price} {attraction.duration && `• ${attraction.duration}`} {attraction.rating && `• ${attraction.rating} ★`}
                  </div>
                )}
                <div className="mt-2 text-xs text-gray-700">{attraction.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DynamicMap;
