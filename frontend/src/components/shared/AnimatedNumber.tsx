import { useEffect, useRef } from 'react'
import { motion, useMotionValue, useTransform, animate } from 'framer-motion'

interface AnimatedNumberProps {
  value: number
  duration?: number
  decimals?: number
  prefix?: string
  suffix?: string
  className?: string
}

export function AnimatedNumber({
  value,
  duration = 800,
  decimals = 0,
  prefix = '',
  suffix = '',
  className = '',
}: AnimatedNumberProps) {
  const motionVal = useMotionValue(0)
  const rounded = useTransform(motionVal, (v) =>
    `${prefix}${v.toFixed(decimals)}${suffix}`
  )
  const prevValue = useRef(0)

  useEffect(() => {
    const controls = animate(motionVal, value, {
      duration: duration / 1000,
      ease: [0.32, 0, 0.67, 0],
      from: prevValue.current,
    })
    prevValue.current = value
    return controls.stop
  }, [value, duration, motionVal])

  return (
    <motion.span className={className} style={{ fontVariantNumeric: 'tabular-nums' }}>
      {rounded}
    </motion.span>
  )
}
