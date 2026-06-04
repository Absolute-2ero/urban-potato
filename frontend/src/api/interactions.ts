import client from './client'

export const logInteraction = (
  restaurantId: string,
  interactionType: 'view' | 'save' | 'click' = 'view',
) =>
  client
    .post('/api/interactions', { restaurant_id: restaurantId, interaction_type: interactionType })
    .catch(() => {})  // fire-and-forget, never block UI
