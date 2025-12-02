
console.log('Loading function');

export const handler = async (event, context) => {
    console.log('event =', JSON.stringify(event));
    console.log('context =', JSON.stringify(context));

    var response = undefined;

    if (event.body !== undefined) {
        // API Gateway format
        console.log('event.body =', event.body);
        const body = JSON.parse(event.body);
        response = {
            "status": "SUCCESS",
            "message": `Refund processed successfully: $${body.amount} for order ${body.orderId}`,
            "amount": body.amount,
            "orderId": body.orderId
        };
    } else {
        // Direct invocation from Gateway
        response = {
            "status": "SUCCESS",
            "message": `Refund processed successfully: $${event.amount} for order ${event.orderId}`,
            "amount": event.amount,
            "orderId": event.orderId
        };
        return response;
    }

    console.log('response =', JSON.stringify(response));
    return {"statusCode": 200, "body": JSON.stringify(response)};
};
