---
id: 23187
severity: "High"
---

# Liquidated positions will still ac-

## Description

The NFTRewardsDistributor contract which is responsible for managing a users rewards using a masterchef algorithm does not get updated when a users underlying position in a pool is liquidated. This results in the position wrongfully continuing to accrue rewards with an outdated asset balance.  
The choice to neglect updating the NFTPositionManager contract when a position is liquidated is the root cause of this issue due to the NFTPositionManager contract not containing up-to-date user balances for calculating rewards.  
```solidity
function earned(uint256 tokenId, bytes32 _assetHash) public view returns (uint256) {
    return _balances[tokenId][_assetHash].mul(rewardPerToken(_assetHash).sub(userRewardPerTokenPaid[tokenId][_assetHash])).div(1e18).add(
        rewards[tokenId][_assetHash]
    );
}
```
The above calculations are done in NFTRewardsDistributor.sol:98 to determine an NFT position's rewards. Due to this bug, the users balance _balances[tokenId][_assetHash] will be incorrect, leading to overinflated rewards.  
Internal pre-conditions  
1. User needs to have a position NFT registered with the NFTPositionManager contract  
2. The NFTPositionManager needs to have rewards accrual enabled for there to be any impact  
3. The users NFT position needs to be liquidated due to their position being unhealthy  
External pre-conditions  
1. Users collateral assets need to drop in enough in price to make their position liquidatable  
2. Any user needs to liquidate the users position  
Attack Path  
1. User creates a position  
2. The NFTPositionManager contract will start accruing rewards for the user  
3. The users position's collateral drops in price enough to make their position unhealthy  
4. The user gets liquidated  
5. The user will continue to accrue rewards pertaining to their NFT's position for as long as they wish because the NFTPositionManager believes they are still providing collateral and borrowing assets.  
6. The user withdraws their accrued rewards whenever they wish  
The liquidated user will essentially be able to steal rewards from the protocol/other users since their position won't be backed by any collateral.

## Proof of Concept

```solidity
function test_UserAccruesRewardsWhileLiquidatedBug() public {
    NFTPositionManager _nftPositionManager = new NFTPositionManager();
    TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(address(_nftPositionManager), admin, bytes(''));
    nftPositionManager = NFTPositionManager(payable(address(proxy)));
    nftPositionManager.initialize(address(poolFactory), address(0x123123), owner, address(tokenA), address(wethToken));
    uint256 mintAmount = 100 ether;
    uint256 supplyAmount = 1 ether;
    uint256 tokenId = 1;
    bytes32 REWARDS_ALLOCATOR_ROLE = keccak256('REWARDS_ALLOCATOR_ROLE');
    //approvals
    _mintAndApprove(owner, tokenA, 30e18, address(nftPositionManager));
    _mintAndApprove(alice, tokenA, 1000 ether, address(pool)); // alice 1000 tokenA
    _mintAndApprove(bob, tokenB, 2000 ether, address(pool)); // bob 2000 tokenB
    _mintAndApprove(bob, tokenA, 2000 ether, address(pool)); // bob 2000 tokenB
    //grant the pool some rewards
    vm.startPrank(owner);
    nftPositionManager.grantRole(REWARDS_ALLOCATOR_ROLE, owner);
    nftPositionManager.notifyRewardAmount(10e18, address(pool), address(tokenA), false);
    vm.stopPrank();
    DataTypes.ExtraData memory data = DataTypes.ExtraData(bytes(''), bytes(''));
    INFTPositionManager.AssetOperationParams memory params = INFTPositionManager.AssetOperationParams(address(tokenA), alice, 550 ether, tokenId, data);
    INFTPositionManager.AssetOperationParams memory params2 = INFTPositionManager.AssetOperationParams(address(tokenB), bob, 750 ether, 2, data);
    INFTPositionManager.AssetOperationParams memory params3 = INFTPositionManager.AssetOperationParams(address(tokenA), bob, 550 ether, 2, data);
    INFTPositionManager.AssetOperationParams memory borrowParams = INFTPositionManager.AssetOperationParams(address(tokenB), alice, 100 ether, tokenId, data);
    vm.startPrank(alice);
    tokenA.approve(address(nftPositionManager), 100000 ether);
    tokenA.approve(address(pool), 100000 ether);
    nftPositionManager.mint(address(pool));
    nftPositionManager.supply(params);
    console.log("Alice deposits %e of token A", params.amount);
    vm.stopPrank();
    vm.startPrank(bob);
    tokenB.approve(address(nftPositionManager), 100000 ether);
    tokenA.approve(address(nftPositionManager), 100000 ether);
    tokenB.approve(address(pool), 100000 ether);
    nftPositionManager.mint(address(pool));
    nftPositionManager.supply(params2);
    nftPositionManager.supply(params3);
    console.log("Bob deposits %e of token A", params3.amount);
    vm.stopPrank();
    vm.prank(alice);
    nftPositionManager.borrow(borrowParams);
    bytes32 assetHashA = nftPositionManager.assetHash(address(pool), address(tokenA), false);
    bytes32 pos = keccak256(abi.encodePacked(nftPositionManager, 'index', uint256(1)));
    console.log("\nAlice rewards earned before liquidation: %e", nftPositionManager.earned(1, assetHashA));
    console.log("Bob rewards earned before Alice is Liquidated: %e\n", nftPositionManager.earned(2, assetHashA));
    oracleA.updateAnswer(3e5);
    vm.prank(bob);
    console.log("Bob liquidates Alice");
    pool.liquidateSimple(address(tokenA), address(tokenB), pos, 550 ether);
    console.log("Skip ahead until end of rewards cycle...");
    vm.warp(block.timestamp+14 days);
    console.log("\nAlice rewards earned after liquidation: %e", nftPositionManager.earned(1, assetHashA));
    console.log("Bob rewards earned after Alice is liquidated: %e", nftPositionManager.earned(2, assetHashA));
    console.log("Alice rewards equal to Bob rewards: ", nftPositionManager.earned(1, assetHashA) == nftPositionManager.earned(2, assetHashA));
}
```
Logs  
Output: Alice deposits 5.5e20 of token A Bob deposits 5.5e20 of token A  
Alice rewards earned before liquidation: 0e0 Bob rewards earned before Alice is Liquidated: 0e0  
Bob liquidates Alice Skip ahead until end of rewards cycle...  
Alice rewards earned after liquidation: 4.99999999999953585e18 Bob rewards earned after Alice is liquidated: 4.99999999999953585e18 Alice rewards equal to Bob rewards: true  
The PoC shows that even though Alice was liquidated, she continued to accrue the same amount of rewards as Bob over the time period.

## Recommendation

When necessary, the liquidation function should callback to the NFT position contract to update the liquidated users position with the contract so they don't continue to accrue rewards.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of rewards continuing to be allocated to an NFT‑backed position after that position has been liquidated because the contract that stores per‑NFT balances is never updated when liquidation occurs. The root cause is that the NFTPositionManager contract, which holds the _balances mapping used in the reward formula, does not receive a callback from the liquidation routine, so the balance value remains equal to the pre‑liquidation amount. The reward calculation multiplies this stale balance by the difference between the global reward per token and the user‑specific paid amount, which yields a positive reward amount even though the position no longer holds any collateral. An attacker can exploit this by opening a leveraged position, allowing the collateral price to drop, triggering liquidation, and then simply waiting for the reward period to elapse before calling the claim function. The user will receive reward tokens that should have been forfeited, effectively stealing value from the protocol and other participants. This scenario occurs whenever a position becomes under‑collateralized, the price feed reflects a sufficient drop, and a liquidator calls the liquidation function. Affected parties include the protocol (loss of reward tokens), other users sharing the reward pool, and any user whose position is liquidated. The issue was discovered during a manual audit that examined the reward accrual path and noticed that the balance variable is never cleared on liquidation. It is hard to notice because the UI may still display the NFT as existing and the reward balance as growing, which can be mistaken for normal accrual. The bug belongs to the class of stale‑state or missing‑state‑update errors that cause over‑allocation of rewards. From the user’s perspective, the expectation is that rewards stop once the position is liquidated, but the reality is that the reward balance continues to increase and can be withdrawn, leading to unexpected token gains. The attack flow can be described as: (1) open a leveraged position, (2) let the collateral price fall, (3) trigger liquidation, (4) do nothing else, (5) allow the reward period to run, (6) claim the inflated rewards. The recommended mitigation is to have the liquidation function invoke a callback on the rewards manager to reset the user’s balance to zero or mark the position as inactive before any further reward calculations, thereby aligning the reward accounting with the actual collateral state.
