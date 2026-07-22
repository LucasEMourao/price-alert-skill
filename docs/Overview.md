## Overview

#### Function List

Get offer list  
Get short link  
Get conversion report  

#### API Calling Process

Shopee Affiliate Open API platform USES the GraphQL specification to handle requests.  
GraphQL is based on the HTTP protocol, so it's easy to integrate with various HTTP libraries like cURL and Requests. There are also a variety of open source clients to choose from [https://graphql.org/code/#graphql-clients.](https://graphql.org/code/#graphql-clients.)  
For more specifications on GraphQL, please refer to [https://graphql.org/.](https://graphql.org/)

#### Authentication

All requests use authorization headers to provide authentication information. For details, please refer to [#Authentication.](https://affiliate.shopee.com.br/open_api/document?type=authentication)

#### Rate Limit

The system limits the number of API calls issued within a specified time period. The current system limit is 8000 times/hour.  
If the limit is exceeded, the system will refuse to process the request. The client needs to wait for the next time window to resend the request.

#### Timestamp and Timezone

Shopee is using local time in UTC+ time format for each local region to store the data.  
But regardless of your timezone, a timestamp represents a moment that is the same everywhere.  
Get Timestamp [here](https://www.unixtimestamp.com/) for Shopee Open API platform.

#### Important notes Must Read

#### Scrollid

If you need to query multiple pages of data, you need to Query Twice or more!  
The first query can get the content of the first page and scrollid, and the maximum number of data returned per page is 500.  
Scrollid is used to help query the content of the second page and later. In order to get the content of the second page and later you Must Query with Scrollid.  
Scrollid is one-time valid, the valid time is only 30 seconds.  
So after the first request for scrollid, please query the content of the second and later page within 30 seconds.  
The query without scrollid requires an interval of longer than 30 seconds.

#### Queryable Time range of conversion report

The available querying data time range is Recent 3 Months.  
The time range that can be queried in the Open API is consistent with the time range of affiliate system portal.  
If you query longer than the range, system will send error.

#### Tool to request and check

Here is an useful tool to make request and check: