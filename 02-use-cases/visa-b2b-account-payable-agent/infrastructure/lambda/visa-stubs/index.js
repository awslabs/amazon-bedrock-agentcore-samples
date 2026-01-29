/**
 * Visa B2B Stub API - Main Entry Point
 * 
 * This file exports all the stub API handlers for the Visa B2B Virtual Account Payment API.
 */

// Virtual Card Requisition handler
exports.virtualCardRequisition = async (event) => {
  console.log('VirtualCardRequisition called with:', JSON.stringify(event, null, 2));
  
  const body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
  const { messageId, buyerId, amount, currency } = body;
  
  // Generate random card details
  const requisitionId = Math.floor(Math.random() * 1000000000).toString();
  const accountNumber = '4' + Math.floor(Math.random() * 1000000000000000).toString().padStart(15, '0');
  const expirationDate = '12/2025';
  
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
    body: JSON.stringify({
      VCardRequistionResponse: {
        messageId,
        requisitionId,
        accountNumber,
        expirationDate,
        statusCode: '00',
        statusDesc: 'Success',
      },
    }),
  };
};

// Process Payments handler
exports.processPayments = async (event) => {
  console.log('ProcessPayments called with:', JSON.stringify(event, null, 2));
  
  const body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
  const { messageId, buyerId, virtualCardId, amount } = body;
  
  // Generate tracking number
  const trackingNumber = Math.floor(Math.random() * 10000000000).toString();
  
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
    body: JSON.stringify({
      ProcessResponse: {
        messageId,
        trackingNumber,
        cardHolderName: 'ACME CORPORATION',
        statusCode: '00',
        statusDesc: 'Success',
      },
    }),
  };
};

// Get Payment Details handler
exports.getPaymentDetails = async (event) => {
  console.log('GetPaymentDetails called with:', JSON.stringify(event, null, 2));
  
  const body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
  const { messageId, buyerId, trackingNumber } = body;
  
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
    body: JSON.stringify({
      GetPaymentResponse: {
        messageId,
        trackingNumber,
        statusCode: '00',
        statusDesc: 'Payment Completed Successfully',
        amount: 1000.00,
        currency: 'USD',
        paymentDate: new Date().toISOString(),
      },
    }),
  };
};

// Get Security Code (CVV2) handler
exports.getSecurityCode = async (event) => {
  console.log('GetSecurityCode called with:', JSON.stringify(event, null, 2));
  
  const body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
  const { messageId, accountNumber, expirationDate } = body;
  
  // Generate a random 3-digit CVV2
  const cvv2 = Math.floor(100 + Math.random() * 900).toString();
  
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
    body: JSON.stringify({
      GetSecurityCodeResponse: {
        messageId,
        cvv2,
        statusCode: '00',
        statusDesc: 'Success',
      },
    }),
  };
};

