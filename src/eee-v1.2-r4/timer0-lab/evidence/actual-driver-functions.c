static int mtk_get_eee(struct net_device *dev, struct ethtool_keee *eee)
{
	struct mtk_mac *mac = netdev_priv(dev);
	u32 reg;
	int ret;

	ret = phylink_ethtool_get_eee(mac->phylink, eee);
	if (ret)
		return ret;

	reg = mtk_r32(mac->hw, MTK_MAC_EEECR(mac->id));
	eee->tx_lpi_enabled = mac->tx_lpi_enabled;
	eee->tx_lpi_timer = FIELD_GET(MAC_EEE_LPI_TXIDLE_THD, reg) * 1000;

	return 0;
}

static int mtk_set_eee(struct net_device *dev, struct ethtool_keee *eee)
{
	struct mtk_mac *mac = netdev_priv(dev);
	u32 txidle_thd_ms, reg;
	int ret;

	/* Tx idle timer in ms */
	txidle_thd_ms = DIV_ROUND_UP(eee->tx_lpi_timer, 1000);
	if (!FIELD_FIT(MAC_EEE_LPI_TXIDLE_THD, txidle_thd_ms))
		return -EINVAL;

	reg = FIELD_PREP(MAC_EEE_LPI_TXIDLE_THD, txidle_thd_ms);

	/* PHY Wake-up time, this field does not have a reset value, so use the
	 * reset value from MT7531 (36us for 100BaseT and 17us for 1000BaseT).
	 */
	reg |= FIELD_PREP(MAC_EEE_WAKEUP_TIME_1000, 17) |
	       FIELD_PREP(MAC_EEE_WAKEUP_TIME_100, 36);

	if (!txidle_thd_ms)
		/* Force LPI Mode without a delay */
		reg |= MAC_EEE_LPI_MODE;

	ret = phylink_ethtool_set_eee(mac->phylink, eee);
	if (ret)
		return ret;

	mac->tx_lpi_enabled = eee->tx_lpi_enabled;
	mac->txidle_thd_ms = txidle_thd_ms;
	mtk_w32(mac->hw, reg, MTK_MAC_EEECR(mac->id));
	if (eee->eee_enabled && eee->eee_active && eee->tx_lpi_enabled)
		mtk_m32(mac->hw, 0, MAC_MCR_EEE100M | MAC_MCR_EEE1G, MTK_MAC_MCR(mac->id));
	else
		mtk_m32(mac->hw, MAC_MCR_EEE100M | MAC_MCR_EEE1G, 0, MTK_MAC_MCR(mac->id));

	return 0;
}
