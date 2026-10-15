import React from 'react';
import { Landmark, MessageSquare, Calendar, Clock, ArrowRight } from 'lucide-react';

export default function FeatureCards({ 
  onExploreTemples, 
  onOpenAssistant, 
  onOpenTripPlanner, 
  onOpenChatHistory 
}) {
  const features = [
    {
      id: 'explore',
      title: 'Explore Temples',
      subtitle: 'Discover temples, history, timings and travel info.',
      icon: Landmark,
      colorClass: 'feature-peach',
      action: onExploreTemples,
    },
    {
      id: 'assistant',
      title: 'AI Travel Assistant',
      subtitle: 'Get instant answers about temples, travel and more.',
      icon: MessageSquare,
      colorClass: 'feature-blue',
      action: onOpenAssistant,
    },
    {
      id: 'planner',
      title: 'Trip Planner',
      subtitle: 'Create personalized itineraries with budget plans.',
      icon: Calendar,
      colorClass: 'feature-green',
      action: onOpenTripPlanner,
    },
    {
      id: 'history',
      title: 'Chat History',
      subtitle: 'Return to your previous conversations.',
      icon: Clock,
      colorClass: 'feature-purple',
      action: onOpenChatHistory,
    },
  ];

  return (
    <div className="feature-cards-grid">
      {features.map((item) => {
        const Icon = item.icon;
        return (
          <div 
            key={item.id} 
            className={`feature-card ${item.colorClass}`}
            onClick={item.action}
          >
            <div className="feature-card-content">
              <div className="feature-icon-circle">
                <Icon size={22} />
              </div>
              <div className="feature-text-block">
                <span className="feature-title">{item.title}</span>
                <span className="feature-subtitle">{item.subtitle}</span>
              </div>
            </div>
            <div className="feature-arrow-btn">
              <ArrowRight size={14} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
