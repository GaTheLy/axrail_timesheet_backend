import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';

// Custom metrics
const errorRate = new Rate('errors');
const loginDuration = new Trend('login_duration');
const timesheetDuration = new Trend('timesheet_duration');
const graphqlDuration = new Trend('graphql_duration');

// Configuration
const FRONTEND_URL = __ENV.FRONTEND_URL || 'https://dwy237unaf2sp.cloudfront.net';
const APPSYNC_URL = __ENV.APPSYNC_URL || '';
const COGNITO_CLIENT_ID = __ENV.COGNITO_CLIENT_ID || '';
const COGNITO_REGION = __ENV.COGNITO_REGION || 'ap-southeast-1';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'test@example.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || 'TestPassword123!';

// Store auth token globally
let authToken = null;

export const options = {
  scenarios: {
    // Frontend load test
    frontend_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 10 },
        { duration: '5m', target: 10 },
        { duration: '2m', target: 20 },
        { duration: '5m', target: 20 },
        { duration: '2m', target: 0 },
      ],
      startTime: '0s',
      exec: 'frontendFlow',
      tags: { test_type: 'frontend' },
    },
    // Backend GraphQL load test
    backend_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 15 },
        { duration: '5m', target: 15 },
        { duration: '2m', target: 30 },
        { duration: '5m', target: 30 },
        { duration: '2m', target: 0 },
      ],
      startTime: '0s',
      exec: 'backendFlow',
      tags: { test_type: 'backend' },
    },
    // Frontend stress test
    frontend_stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 0 },
      ],
      startTime: '16m',
      exec: 'frontendFlow',
      tags: { test_type: 'frontend_stress' },
    },
    // Backend stress test
    backend_stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 0 },
      ],
      startTime: '16m',
      exec: 'backendFlow',
      tags: { test_type: 'backend_stress' },
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    errors: ['rate<0.1'],
    login_duration: ['p(95)<3000'],
    timesheet_duration: ['p(95)<2000'],
    graphql_duration: ['p(95)<1500'],
  },
};

function getCsrfToken(response) {
  const match = response.body.match(/name="_token"\s+value="([^"]+)"/);
  return match ? match[1] : null;
}

// Authenticate with Cognito and get JWT token
function getCognitoToken() {
  const cognitoUrl = `https://cognito-idp.${COGNITO_REGION}.amazonaws.com/`;
  
  const payload = JSON.stringify({
    AuthFlow: 'USER_PASSWORD_AUTH',
    ClientId: COGNITO_CLIENT_ID,
    AuthParameters: {
      USERNAME: TEST_EMAIL,
      PASSWORD: TEST_PASSWORD,
    },
  });

  const params = {
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
    },
  };

  const res = http.post(cognitoUrl, payload, params);
  
  if (res.status === 200) {
    const body = JSON.parse(res.body);
    if (body.AuthenticationResult && body.AuthenticationResult.IdToken) {
      return body.AuthenticationResult.IdToken;
    }
  }
  
  console.log(`Cognito auth failed: ${res.status} - ${res.body}`);
  return null;
}

function graphqlRequest(query, variables = {}) {
  if (!authToken) {
    authToken = getCognitoToken();
  }
  
  if (!authToken) {
    console.log('No auth token available');
    return { status: 401, body: '{}' };
  }

  const payload = JSON.stringify({ query, variables });
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': authToken,
    },
  };
  
  const start = Date.now();
  const res = http.post(APPSYNC_URL, payload, params);
  graphqlDuration.add(Date.now() - start);
  
  return res;
}

// ============================================================
// FRONTEND FLOW
// ============================================================
export function frontendFlow() {
  let csrfToken = null;

  group('Frontend - Login Page', function () {
    const res = http.get(`${FRONTEND_URL}/login`);
    check(res, { 'login page loads': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
    csrfToken = getCsrfToken(res);
    sleep(1);
  });

  group('Frontend - Authentication', function () {
    if (!csrfToken) return;

    const start = Date.now();
    const res = http.post(`${FRONTEND_URL}/login`, {
      _token: csrfToken,
      email: TEST_EMAIL,
      password: TEST_PASSWORD,
    }, { redirects: 5 });

    loginDuration.add(Date.now() - start);
    check(res, { 'login successful': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  group('Frontend - Dashboard', function () {
    const res = http.get(`${FRONTEND_URL}/dashboard`);
    check(res, { 'dashboard loads': (r) => r.status === 200 || r.status === 302 });
    errorRate.add(res.status !== 200 && res.status !== 302);
    sleep(2);
  });

  group('Frontend - Timesheet', function () {
    const start = Date.now();
    const res = http.get(`${FRONTEND_URL}/timesheet`);
    timesheetDuration.add(Date.now() - start);
    check(res, { 'timesheet loads': (r) => r.status === 200 || r.status === 302 });
    sleep(1);

    const projects = http.get(`${FRONTEND_URL}/timesheet/projects`);
    check(projects, { 'projects list loads': (r) => r.status === 200 || r.status === 302 });
    sleep(1);
  });

  group('Frontend - History', function () {
    const res = http.get(`${FRONTEND_URL}/timesheet/history`);
    check(res, { 'history loads': (r) => r.status === 200 || r.status === 302 });
    sleep(1);
  });

  group('Frontend - Settings', function () {
    const res = http.get(`${FRONTEND_URL}/settings`);
    check(res, { 'settings loads': (r) => r.status === 200 || r.status === 302 });
    sleep(1);
  });

  sleep(Math.random() * 3 + 1);
}

// ============================================================
// BACKEND GRAPHQL FLOW
// ============================================================
export function backendFlow() {
  if (!APPSYNC_URL || !COGNITO_CLIENT_ID) {
    console.log('Skipping backend tests - APPSYNC_URL or COGNITO_CLIENT_ID not set');
    return;
  }

  // Get fresh token for this VU
  authToken = getCognitoToken();
  if (!authToken) {
    errorRate.add(true);
    return;
  }

  group('GraphQL - List Users', function () {
    const query = `
      query ListUsers {
        listUsers {
          items {
            userId
            email
            fullName
            userType
            status
          }
          nextToken
        }
      }
    `;
    const res = graphqlRequest(query);
    check(res, {
      'listUsers status 200': (r) => r.status === 200,
      'listUsers no errors': (r) => !JSON.parse(r.body).errors,
    });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  group('GraphQL - List Departments', function () {
    const query = `
      query ListDepartments {
        listDepartments {
          departmentId
          departmentName
          approval_status
        }
      }
    `;
    const res = graphqlRequest(query);
    check(res, {
      'listDepartments status 200': (r) => r.status === 200,
      'listDepartments no errors': (r) => !JSON.parse(r.body).errors,
    });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  group('GraphQL - List Projects', function () {
    const query = `
      query ListProjects {
        listProjects {
          items {
            projectId
            projectCode
            projectName
            status
            approval_status
          }
          nextToken
        }
      }
    `;
    const res = graphqlRequest(query);
    check(res, {
      'listProjects status 200': (r) => r.status === 200,
      'listProjects no errors': (r) => !JSON.parse(r.body).errors,
    });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  group('GraphQL - Get Current Period', function () {
    const query = `
      query GetCurrentPeriod {
        getCurrentPeriod {
          periodId
          startDate
          endDate
          submissionDeadline
          periodString
          isLocked
        }
      }
    `;
    const res = graphqlRequest(query);
    check(res, {
      'getCurrentPeriod status 200': (r) => r.status === 200,
      'getCurrentPeriod no errors': (r) => !JSON.parse(r.body).errors,
    });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  group('GraphQL - List Timesheet Periods', function () {
    const query = `
      query ListTimesheetPeriods {
        listTimesheetPeriods {
          periodId
          startDate
          endDate
          periodString
          isLocked
        }
      }
    `;
    const res = graphqlRequest(query);
    check(res, {
      'listTimesheetPeriods status 200': (r) => r.status === 200,
      'listTimesheetPeriods no errors': (r) => !JSON.parse(r.body).errors,
    });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  group('GraphQL - List My Submissions', function () {
    const query = `
      query ListMySubmissions {
        listMySubmissions {
          submissionId
          periodId
          status
          totalHours
          chargeableHours
        }
      }
    `;
    const res = graphqlRequest(query);
    check(res, {
      'listMySubmissions status 200': (r) => r.status === 200,
    });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  group('GraphQL - List Project Assignments', function () {
    const query = `
      query ListProjectAssignments {
        listProjectAssignments {
          assignmentId
          employeeId
          projectId
          supervisorId
        }
      }
    `;
    const res = graphqlRequest(query);
    check(res, {
      'listProjectAssignments status 200': (r) => r.status === 200,
      'listProjectAssignments no errors': (r) => !JSON.parse(r.body).errors,
    });
    errorRate.add(res.status !== 200);
    sleep(1);
  });

  sleep(Math.random() * 2 + 1);
}

export function teardown() {
  console.log('Load test completed');
}

export function handleSummary(data) {
  return {
    'load-tests/results/summary.html': htmlReport(data),
    'load-tests/results/summary.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
