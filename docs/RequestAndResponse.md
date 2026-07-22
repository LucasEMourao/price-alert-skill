## Request and Response

#### Request

Open API request need to use the `“POST”` method, and the content type is `application/json`,  
Endpoint is `https://open-api.affiliate.shopee.com.br/graphql` and no matter what operation is performed, the endpoint remains the same.

The request format is

```
{
"query": "...",
"operationName": "...",
"variables": { "myVariable": "someValue", ... }
}
```

where `operationName` and `variables` are optional fields.  
Only when there are multiple operations in the query, `OperationName` is required.

#### Response

If Open API has received your request, it will return a response with an HTTP Status Code of 200. The data and error information will be returned in `JSON` format which is

```
{
"data": { ... },
"errors": [ ... ]
}
```

If no error occurs, the error information won’t be returned.

#### Error Structure

Error Codes