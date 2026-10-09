import {
  Car,
  GraduationCap,
  Home,
  Plane,
  ShieldAlert,
  Target
} from 'lucide-react'

export function getGoalIcon(goal) {
  const title = (goal?.goal_name || goal?.custom_name || goal?.goal_id || '').toLowerCase()
  let Icon

  if (title.includes('home') || title.includes('ev') || title.includes('mənzil')) {
    Icon = Home
  } else if (title.includes('car') || title.includes('avtomobil') || title.includes('maşın')) {
    Icon = Car
  } else if (title.includes('travel') || title.includes('səyahət') || title.includes('tətil')) {
    Icon = Plane
  } else if (title.includes('education') || title.includes('təhsil')) {
    Icon = GraduationCap
  } else if (title.includes('emergency') || title.includes('təcili')) {
    Icon = ShieldAlert
  } else {
    Icon = Target
  }

  return <Icon size={20} strokeWidth={2.2} />
}
