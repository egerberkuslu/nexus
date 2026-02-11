import { Routes, Route } from 'react-router-dom'
import Layout from '@components/Layout'
import Home from '@pages/Home'
import Features from '@pages/Features'
import { ProjectsPage } from '@features/projects'
import TopologyEditor from '@pages/TopologyEditor'
import Monitoring from '@pages/Monitoring'
import NetworkManager from '@pages/NetworkManager'
import Infrastructure from '@pages/Infrastructure'
import Snapshots from '@pages/Snapshots'
import ScheduleManager from '@pages/ScheduleManager'
import AiSettings from '@pages/AiSettings'
import AiConsoleAdmin from '@pages/AiConsoleAdmin'
import MlModels from '@pages/MlModels'
import DataLab from '@pages/DataLab'
import ApiDocs from '@pages/ApiDocs'
import { NotFound } from '@pages/NotFound'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="features" element={<Features />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="topology/:id" element={<TopologyEditor />} />
        <Route path="monitoring/:id" element={<Monitoring />} />
        <Route path="network-manager" element={<NetworkManager />} />
        <Route path="infrastructure" element={<Infrastructure />} />
        <Route path="ai-console" element={<AiConsoleAdmin />} />
        <Route path="ai-settings" element={<AiSettings />} />
        <Route path="ml-models" element={<MlModels />} />
        <Route path="data-lab" element={<DataLab />} />
        <Route path="docs" element={<ApiDocs />} />
        <Route path="snapshots" element={<Snapshots />} />
        <Route path="snapshots/:topologyId" element={<Snapshots />} />
        <Route path="schedules" element={<ScheduleManager />} />
        <Route path="schedules/:topologyId" element={<ScheduleManager />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default App
