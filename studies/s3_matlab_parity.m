% Study S3 — the same learning problems in MATLAB R2026b (SIMULATED data).
%
% Uses only base MATLAB + Optimization Toolbox (the toolboxes installed on the
% study machine). Statistics and Machine Learning, System Identification and Deep
% Learning toolboxes are NOT used, so the results do not depend on them.
%
%   Part 1  thermal identification on results/s1_telemetry.csv:
%           equation error with mldivide, output error with lsqnonlin,
%           compared with the SciPy numbers in results/s1_thermal_id.json.
%   Part 2  day-ahead ridge forecast on results/s2_history.csv, compared with
%           SciPy's test MAE in results/s2_forecast_value.json.
%   Part 3  MATLAB -> Python interop: call peakpilot.engine directly (pyenv,
%           out-of-process) and check its room series against the CSV.
%
% Run s1_thermal_id.py and s2_forecast_value.py first, then from this folder:
%   PEAKPILOT_PYTHON=/path/to/.venv/bin/python matlab -batch "s3_matlab_parity"
% Writes results/s3_matlab_parity.json.

here = fileparts(mfilename('fullpath'));
res = fullfile(here, 'results');
repo = fullfile(here, '..');
out = struct('label', 'SIMULATED; MATLAB R2026b base + Optimization Toolbox', ...
             'matlab_release', version('-release'));

%% Part 1 — thermal identification
T = readtable(fullfile(res, 's1_telemetry.csv'));
meas = T.room_meas_c; outdoor = T.outdoor_c; u = T.ac_kw;
s1 = jsondecode(fileread(fullfile(res, 's1_thermal_id.json')));
rows = s1.rows;
pick = @(m) rows(arrayfun(@(r) r.noise_c == 0.1 && r.train_min == 960 && strcmp(r.method, m), rows));
sp_ee = pick('EE'); sp_oe = pick('OE');

tic;
X = [outdoor(1:end-1) - meas(1:end-1), -u(1:end-1)];
theta_ee = X \ diff(meas);
t_ee = toc;

opts = optimoptions('lsqnonlin', 'Display', 'off');
tic;
p_oe = lsqnonlin(@(p) simroom(p(1), p(2), p(3), outdoor, u) - meas, ...
                 [theta_ee; meas(1)], [1e-4; 1e-4; 0], [1; 5; 60], opts);
t_oe = toc;

out.thermal = struct( ...
    'ee_a', theta_ee(1), 'ee_b', theta_ee(2), 'ee_s', t_ee, ...
    'oe_a', p_oe(1), 'oe_b', p_oe(2), 'oe_s', t_oe, ...
    'scipy_ee_a', sp_ee.a, 'scipy_ee_b', sp_ee.b, ...
    'scipy_oe_a', sp_oe.a, 'scipy_oe_b', sp_oe.b, ...
    'max_abs_diff_ee', max(abs([theta_ee(1) - sp_ee.a, theta_ee(2) - sp_ee.b])), ...
    'max_abs_diff_oe', max(abs([p_oe(1) - sp_oe.a, p_oe(2) - sp_oe.b])));

%% Part 2 — ridge day-ahead forecast
H = readtable(fullfile(res, 's2_history.csv'));
Y = H{:, startsWith(H.Properties.VariableNames, 'm')};
train = strcmp(H.split, 'train'); test = ~train;
s2 = jsondecode(fileread(fullfile(res, 's2_forecast_value.json')));
lambda = s2.part_b.ridge_lambda;

tic;
Xtr = [ones(nnz(train), 1), H.outdoor_peak_c(train) - 30];
W = (Xtr' * Xtr + lambda * diag([0 1])) \ (Xtr' * Y(train, :));
t_ridge = toc;
Xte = [ones(nnz(test), 1), H.outdoor_peak_c(test) - 30];
mae = mean(abs(Xte * W - Y(test, :)), 'all');
models = s2.part_b.models;
scipy_mae = models.(matlab.lang.makeValidName('ridge on outdoor peak')).mae_kw;
out.forecast = struct('ridge_test_mae_kw', mae, 'scipy_ridge_test_mae_kw', scipy_mae, ...
                      'abs_diff_kw', abs(mae - scipy_mae), 'fit_s', t_ridge);

%% Part 3 — call the PeakPilot engine from MATLAB
py_exe = getenv('PEAKPILOT_PYTHON');
if isempty(py_exe)
    py_exe = fullfile(repo, '.venv', 'bin', 'python');
end
try
    pyenv(Version=py_exe, ExecutionMode="OutOfProcess");
    sys_path = py.sys.path;
    sys_path.insert(int32(0), char(java.io.File(repo).getCanonicalPath()));
    tic;
    run = py.peakpilot.engine.compare(py.peakpilot.scenarios.hot_evening());
    t_py = toc;
    room = cellfun(@double, cell(run.coordinated.room_c))';
    out.interop = struct('ok', true, 'python', char(pyenv().Version), ...
        'coordinated_peak_kw', double(run.coordinated.peak_kw), ...
        'max_abs_diff_room_vs_csv_c', max(abs(room - T.room_true_c)), 'call_s', t_py);
catch err
    out.interop = struct('ok', false, 'error', err.message);
end

fid = fopen(fullfile(res, 's3_matlab_parity.json'), 'w');
fprintf(fid, '%s', jsonencode(out, PrettyPrint=true));
fclose(fid);
disp(jsonencode(out, PrettyPrint=true));

function temps = simroom(a, b, t0, outdoor, u)
% Free-run the engine's RC room model (see engine._step_room_temp).
temps = zeros(size(outdoor));
temps(1) = t0;
for t = 1:numel(outdoor) - 1
    temps(t + 1) = temps(t) + a * (outdoor(t) - temps(t)) - b * u(t);
end
end
